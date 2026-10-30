"""Várias casas ao mesmo tempo: um grupo de threads, uma casa por vez em cada.

`por_casa(casas, tarefa, n, parar)` roda `tarefa(casa)` para cada casa, até
`n` ao mesmo tempo, e devolve os resultados na ordem de `casas`. Os limites
de requisições ficam no cliente HTTP (por site e por servidor), que todas as
threads compartilham.

- Cada linha do log escrita durante a tarefa de uma casa começa com
  `[<host>] ` (veja `registro.casa_atual`).
- A cada `a_cada` segundos, uma linha de progresso geral: casas concluídas,
  em andamento e na fila, mais o texto de `progresso()` (ex.: matérias).
- Ctrl+C: liga o evento `parar` (o cliente não faz mais requisições e as
  esperas acabam), descarta as casas que não começaram, espera as que estão
  em andamento pararem (no máximo o tempo de uma requisição) e repassa o
  `KeyboardInterrupt`. Um Ctrl+C dentro de uma tarefa vale o mesmo.
- Um erro inesperado numa casa (um bug, disco cheio...) vai para o log com
  o traceback, as outras casas continuam, e no fim `FalhaNasCasas` diz quais
  casas pararam. Nada se perde em silêncio.
"""

import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import TypeVar
from urllib.parse import urlparse

from sapyl import registro
from sapyl.cliente_http import Interrompido
from sapyl.padroes import PROGRESSO_A_CADA

T = TypeVar('T')

log = registro.logger('execucao')


class FalhaNasCasas(RuntimeError):
    """Uma ou mais casas pararam por um erro inesperado (as outras terminaram)."""

    def __init__(self, falhas: list[tuple[str, BaseException]]) -> None:
        self.falhas = falhas
        detalhes = '; '.join(f'{casa} ({type(e).__name__}: {e})' for casa, e in falhas)
        super().__init__(
            f'{len(falhas)} casa(s) pararam por um erro inesperado: {detalhes}. '
            'O traceback está no log desta execução.'
        )


def nome_da_casa(casa: str) -> str:
    """Host da casa (`sapl.x.leg.br`), para o prefixo das linhas do log."""
    return urlparse(casa).hostname or casa


def por_casa(
    casas: Sequence[str],
    tarefa: Callable[[str], T],
    n: int,
    parar: threading.Event,
    progresso: Callable[[], str] | None = None,
    a_cada: float = PROGRESSO_A_CADA,
) -> list[T]:
    """Roda `tarefa(casa)` para cada casa, até `n` ao mesmo tempo (veja o módulo).

    Devolve os resultados na ordem de `casas`. Com `n == 1`, uma casa por vez.
    """
    casas = list(casas)
    if not casas:
        return []
    parar.clear()
    n = max(1, min(n, len(casas)))

    trava, ativas = threading.Lock(), [0]

    def rodar(casa: str) -> T:
        if parar.is_set():  # nenhuma casa começa depois de um Ctrl+C
            raise Interrompido
        with trava:
            ativas[0] += 1
        try:
            with registro.casa_atual(nome_da_casa(casa)):
                return tarefa(casa)
        finally:
            with trava:
                ativas[0] -= 1

    executor = ThreadPoolExecutor(max_workers=n, thread_name_prefix='casa')
    futuros: list[Future] = []
    casa_do: dict[Future, str] = {}
    falhas: list[tuple[str, BaseException]] = []
    try:
        # Dentro do `try`: um Ctrl+C enquanto as casas entram na fila também para tudo
        for casa in casas:
            futuro = executor.submit(rodar, casa)
            futuros.append(futuro)
            casa_do[futuro] = casa
        pendentes = set(futuros)
        proximo = time.monotonic() + a_cada
        while pendentes:
            feitos, pendentes = wait(
                pendentes, timeout=min(1.0, a_cada), return_when=FIRST_COMPLETED
            )
            for futuro in feitos:
                erro = futuro.exception()
                if isinstance(erro, KeyboardInterrupt):
                    raise KeyboardInterrupt from erro
                if erro is not None:
                    log.error(
                        'Erro inesperado na casa %s: a casa parou, as outras continuam',
                        casa_do[futuro],
                        exc_info=erro,
                    )
                    falhas.append((casa_do[futuro], erro))
            if time.monotonic() >= proximo:
                proximo = time.monotonic() + a_cada
                log.info(_linha_de_progresso(futuros, progresso))
    except KeyboardInterrupt:
        executor.shutdown(wait=False, cancel_futures=True)  # descarta a fila
        with trava:
            rodando = ativas[0]
        parar.set()
        if rodando:
            log.warning(
                'Parando: esperando %d casa(s) terminarem a requisição em andamento', rodando
            )
        executor.shutdown(wait=True)
        raise
    executor.shutdown(wait=True)
    if falhas:
        ordem = {casa: i for i, casa in enumerate(casas)}
        raise FalhaNasCasas(sorted(falhas, key=lambda f: ordem[f[0]]))
    return [futuro.result() for futuro in futuros]


def _linha_de_progresso(futuros: list[Future], progresso: Callable[[], str] | None) -> str:
    feitas = sum(f.done() for f in futuros)
    rodando = sum(f.running() for f in futuros)
    linha = (
        f'Progresso: {feitas} de {len(futuros)} casas concluídas, {rodando} em andamento, '
        f'{len(futuros) - feitas - rodando} na fila'
    )
    if progresso is not None:
        linha += f'; {progresso()}'
    return linha
