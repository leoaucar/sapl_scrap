"""Andamento da execução: o que cada casa está fazendo, contagens e tempo restante.

As camadas de baixo só escrevem no log (veja `registro.andamento` e
`execucao.por_casa`). `HandlerAndamento` lê esses registros e atualiza um
`Andamento`, que a interface mostra: numa linha a cada minuto (modo texto)
ou num painel ao vivo (modo menus, veja `PainelAoVivo`).

`Tela` decide onde isso aparece e desenha o resumo do fim.

Tempo restante (estimativa): só depois de 1 minuto e de pelo menos uma casa
concluída. O ritmo conta desde a primeira matéria raspada (o tempo das
buscas, antes dela, não entra). Trabalho que falta = matérias conhecidas e ainda não raspadas (das
casas que já terminaram a busca) + casas que ainda não terminaram a busca ×
média de matérias por casa concluída. Dividido pelas matérias por minuto nos
últimos 5 minutos.
"""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sapyl import registro
from sapyl.execucao import nome_da_casa

JANELA_RITMO = 300.0  # segundos usados para medir as matérias por minuto
ESPERA_ESTIMATIVA = 60.0  # antes disso, "calculando"

# Etapas cujos itens medem o ritmo (matérias raspadas ou com autoria buscada)
UNIDADES_DE_TRABALHO = (registro.MATERIAS, registro.AUTORIA)

NOMES_DAS_ETAPAS = {
    registro.TESTE: 'testando',
    registro.BUSCA: 'buscando',
    registro.MATERIAS: 'matérias',
    registro.PDFS: 'PDFs',
    registro.AUTORIA: 'autoria',
}


@dataclass
class Casa:
    """O que se sabe de uma casa nesta execução."""

    etapa: str = ''
    feitos: int = 0
    total: int = 0
    buscas: int = 0
    materias: int = 0  # matérias a raspar (ou com autoria a buscar) nesta execução
    materias_ok: int = 0
    materias_erro: int = 0
    pdfs_ok: int = 0
    pdfs_erro: int = 0
    autoria: int = 0
    busca_terminada: bool = False

    def nome_da_etapa(self) -> str:
        """`matérias`, `buscando`, `PDFs`... ou `começando`."""
        return NOMES_DAS_ETAPAS.get(self.etapa, self.etapa) if self.etapa else 'começando'

    def texto_da_etapa(self) -> str:
        """`matérias 45/120`, `buscando 2/3`, ou `começando`."""
        nome = self.nome_da_etapa()
        return f'{nome} {self.feitos}/{self.total}' if self.total else nome

    def resumo(self) -> str:
        """`3 buscas, 120 matérias (2 com erro), 40 PDFs` (só o que houve)."""
        partes = []
        if self.buscas:
            partes.append(f'{self.buscas} busca{"s" if self.buscas != 1 else ""}')
        materias = self.materias_ok + self.materias_erro
        if materias or self.etapa == registro.MATERIAS:
            texto = f'{materias} matéria{"s" if materias != 1 else ""}'
            if self.materias_erro:
                texto += f' ({self.materias_erro} com erro)'
            partes.append(texto)
        pdfs = self.pdfs_ok + self.pdfs_erro
        if pdfs:
            texto = f'{pdfs} PDF{"s" if pdfs != 1 else ""}'
            if self.pdfs_erro:
                texto += f' ({self.pdfs_erro} com erro)'
            partes.append(texto)
        if self.autoria:
            partes.append(f'autoria de {self.autoria} matéria{"s" if self.autoria != 1 else ""}')
        return ', '.join(partes) or 'nada a fazer'


@dataclass
class Foto:
    """O andamento num instante, para desenhar o painel ou a linha."""

    total_casas: int
    concluidas: int
    em_andamento: list[tuple[str, str, int, int]]  # (host, etapa, feitos, total)
    teste: tuple[int, int]  # casas testadas, total
    decorrido: float
    restante: float | None
    contagens: list[tuple[str, str]]  # (rótulo, texto): Buscas, Matérias, PDFs
    titulo: str = ''


@dataclass
class Andamento:
    """Estado do andamento, alimentado pelos registros do log (seguro entre threads).

    `contagens`: (rótulo, texto) das contagens do projeto todo (do arquivo de
    estado), para a retomada mostrar o total e não só o desta execução. Sem
    elas (autoria), o andamento conta o que viu nesta execução. `titulo`: a
    linha de cima do painel (projeto, estados, casas, palavras).
    """

    contagens: Callable[[], list[tuple[str, str]]] = lambda: []
    relogio: Callable[[], float] = time.monotonic
    total_casas: int = 0
    casas: dict[str, Casa] = field(default_factory=dict)
    concluidas: dict[str, Casa] = field(default_factory=dict)
    teste_feitos: int = 0
    teste_total: int = 0
    titulo: str = ''

    def __post_init__(self) -> None:
        self._trava = threading.Lock()
        self.inicio = self.relogio()
        self._feitas: deque[tuple[float, int]] = deque()
        self._total_feitas = 0
        self._primeira_feita: float | None = None  # quando saiu a 1ª matéria

    def comecar(self, total_casas: int) -> None:
        """Começa a contar uma fila de `total_casas` casas."""
        with self._trava:
            self.total_casas = total_casas
            self.casas.clear()
            self.concluidas.clear()

    def receber(self, record: logging.LogRecord, host: str) -> None:
        """Atualiza o andamento com uma linha do log da casa `host`."""
        evento = getattr(record, registro.EVENTO_CASA, None)
        dados = getattr(record, registro.ANDAMENTO, None)
        if evento is None and dados is None:
            return
        host = getattr(record, registro.HOST, None) or host
        with self._trava:
            if evento == 'inicio':
                self.casas[host] = Casa()
            elif evento == 'fim':
                self.concluidas[host] = self.casas.pop(host, Casa())
            if dados is not None:
                self._receber_andamento(host, *dados)

    def _receber_andamento(
        self, host: str, etapa: str, feitos: int, total: int, status: str | None
    ) -> None:
        if etapa == registro.TESTE:
            self.teste_feitos = max(self.teste_feitos, feitos)
            self.teste_total = total
            return
        casa = self.casas.setdefault(host, Casa())
        if etapa != registro.BUSCA and casa.etapa in ('', registro.BUSCA):
            casa.busca_terminada = True
        casa.etapa, casa.feitos, casa.total = etapa, feitos, total
        if etapa in UNIDADES_DE_TRABALHO:
            casa.materias = max(casa.materias, total)
            casa.busca_terminada = True
        if status is None:
            return
        if etapa in UNIDADES_DE_TRABALHO:
            agora = self.relogio()
            if self._primeira_feita is None:
                self._primeira_feita = agora
            self._total_feitas += 1
            self._feitas.append((agora, self._total_feitas))
        if etapa == registro.BUSCA:
            casa.buscas += 1
        elif etapa == registro.MATERIAS:
            if status == 'ok':
                casa.materias_ok += 1
            else:
                casa.materias_erro += 1
        elif etapa == registro.PDFS:
            if status == 'erro':
                casa.pdfs_erro += 1
            else:
                casa.pdfs_ok += 1
        elif etapa == registro.AUTORIA:
            casa.autoria += 1

    def resumo_da_casa(self, casa: str) -> str:
        """Texto da linha "Concluída" de uma casa (endereço ou host)."""
        host = nome_da_casa(casa)
        with self._trava:
            dados = self.casas.get(host) or self.concluidas.get(host) or Casa()
            return dados.resumo()

    def _ritmo(self, agora: float) -> float:
        """Matérias por segundo nos últimos `JANELA_RITMO` segundos."""
        while self._feitas and self._feitas[0][0] < agora - JANELA_RITMO:
            self._feitas.popleft()
        if not self._feitas:
            return 0.0
        # conta só desde a 1ª matéria: o tempo das buscas, antes dela, não é ritmo
        desde = self._primeira_feita if self._primeira_feita is not None else self.inicio
        janela = max(min(JANELA_RITMO, agora - desde), 1.0)
        antes = self._feitas[0][1] - 1
        return (self._total_feitas - antes) / janela if janela > 0 else 0.0

    def restante(self) -> float | None:
        """Segundos estimados até o fim, ou None enquanto não dá para estimar."""
        with self._trava:
            agora = self.relogio()
            if agora - self.inicio < ESPERA_ESTIMATIVA or not self.concluidas:
                return None
            ritmo = self._ritmo(agora)
            if ritmo <= 0:
                return None
            media = sum(c.materias for c in self.concluidas.values()) / len(self.concluidas)
            falta = 0.0
            for casa in self.casas.values():
                if casa.busca_terminada:
                    feitas = casa.materias_ok + casa.materias_erro + casa.autoria
                    falta += max(casa.materias - feitas, 0)
                else:
                    falta += media
            nao_comecaram = self.total_casas - len(self.casas) - len(self.concluidas)
            falta += max(nao_comecaram, 0) * media
            return falta / ritmo

    def _contagens_vistas(self) -> list[tuple[str, str]]:
        """Sem contagens do projeto (autoria): o que esta execução já fez."""
        todas = [*self.casas.values(), *self.concluidas.values()]
        autoria = sum(c.autoria for c in todas)
        if not autoria:
            return []
        return [('Autoria', f'{autoria} matéria{"s" if autoria != 1 else ""} feitas')]

    def foto(self) -> Foto:
        """O andamento agora (para o painel ou a linha)."""
        restante = self.restante()
        contagens = self.contagens()
        with self._trava:
            return Foto(
                # sem `comecar` (autoria), o total é o que já apareceu
                total_casas=max(self.total_casas, len(self.casas) + len(self.concluidas)),
                concluidas=len(self.concluidas),
                em_andamento=[
                    (h, c.nome_da_etapa(), c.feitos, c.total) for h, c in self.casas.items()
                ],
                teste=(self.teste_feitos, self.teste_total),
                decorrido=self.relogio() - self.inicio,
                restante=restante,
                contagens=contagens or self._contagens_vistas(),
                titulo=self.titulo,
            )

    def progresso(self) -> str:
        """Segunda linha do bloco de progresso do modo texto: contagens e tempo.

        `Buscas 92 de 230 completas · Matérias 145 raspadas · … · Tempo 3 min 20 s,
        faltam ~5 min (estimativa)`.
        """
        foto = self.foto()
        partes = [f'{rotulo} {texto}' for rotulo, texto in foto.contagens]
        tempo = f'Tempo {_duracao(foto.decorrido)}'
        restante = texto_restante(foto.restante)
        partes.append(f'{tempo}, faltam {restante}' if foto.restante else f'{tempo}, {restante}')
        return ' · '.join(partes)


def texto_restante(segundos: float | None) -> str:
    """`~1 h 20 min (estimativa)`, `~5 min (estimativa)`, ou `calculando`."""
    if segundos is None:
        return 'calculando'
    minutos = max(1, round(segundos / 60))
    horas, minutos = divmod(minutos, 60)
    texto = f'{horas} h {minutos:02d} min' if horas else f'{minutos} min'
    return f'~{texto} (estimativa)'


class HandlerAndamento(logging.Handler):
    """Passa os registros de andamento do log para um `Andamento` (todos os níveis)."""

    def __init__(self, andamento: Andamento) -> None:
        super().__init__(logging.DEBUG)
        self.andamento = andamento

    def emit(self, record: logging.LogRecord) -> None:
        """Roda na thread que escreveu a linha: a casa é a dela."""
        try:
            self.andamento.receber(record, registro.casa_desta_thread())
        except Exception:  # o andamento nunca derruba a execução
            self.handleError(record)


@contextmanager
def acompanhar(
    contagens: Callable[[], list[tuple[str, str]]] = lambda: [], titulo: str = ''
) -> Iterator[Andamento]:
    """Liga um `Andamento` ao log do programa durante o bloco."""
    andamento = Andamento(contagens, titulo=titulo)
    handler = HandlerAndamento(andamento)
    logger = registro.logger()
    if logger.level == logging.NOTSET:  # sem `registro.configurar` (testes)
        logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield andamento
    finally:
        logger.removeHandler(handler)


# ---- Na tela: painel ao vivo (modo menus) ou linhas simples (modo texto) ----

# Marca de uma linha do log que não vai para o terminal (o resumo, desenhado à parte)
SO_ARQUIVO = 'so_arquivo'
LARGURA_BARRA = 30


class HandlerTerminal(logging.Handler):
    """Linhas do log no console do `rich`, acima do painel (nível INFO).

    Com o painel ligado, a linha de progresso de cada minuto fica de fora (o
    painel já mostra tudo). Linhas marcadas com `SO_ARQUIVO` nunca aparecem.
    """

    def __init__(self, console: Any) -> None:
        super().__init__(logging.INFO)
        self.console = console
        self.painel_ligado = False
        self.setFormatter(logging.Formatter(registro.FORMATO_TERMINAL))

    def emit(self, record: logging.LogRecord) -> None:
        """Escreve a linha (sem interpretar colchetes como formatação)."""
        if getattr(record, SO_ARQUIVO, False):
            return
        if self.painel_ligado and getattr(record, registro.PROGRESSO, False):
            return
        try:
            self.console.print(self.format(record), markup=False, highlight=False)
        except Exception:
            self.handleError(record)


def _duracao(segundos: float) -> str:
    return registro.formatar_duracao(segundos)


LARGURA_ROTULO = 10  # "Matérias  "
LARGURA_BARRA_CASA = 12


def _por_cento(feitos: int, total: int) -> str:
    return f'{round(100 * feitos / total)}%' if total else '0%'


def painel(foto: Foto) -> Any:
    """O painel em seções (FR-24): título, casas e tempo, contagens, casas em andamento.

    Exemplo::

        Projeto val_tui · AC · 10 casas · 23 palavras
        ─────────────────────────────────────────────
        Casas      ━━━━━━━━━━━━╺━━━━━━━━━━━━━━━━━  4 de 10 concluídas (40%)
        Tempo      3 min 20 s · faltam ~5 min (estimativa)

        Buscas     92 de 230 completas
        Matérias   145 raspadas · 2 com erro
        PDFs       não pedidos

        Em andamento (1)
          sapl.feijo.ac.leg.br  buscando  12/23  ━━━━━━╺━━━━━
    """
    from rich.console import Group
    from rich.progress_bar import ProgressBar
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    partes: list[Any] = []
    if foto.titulo:
        partes += [Text(foto.titulo, style='bold'), Rule(style='dim', align='left')]

    blocos = Table.grid(padding=(0, 1))
    blocos.add_column(width=LARGURA_ROTULO, style='bold')
    blocos.add_column()
    testadas, teste_total = foto.teste
    if foto.total_casas == 0 and teste_total:
        rotulo, feitos, total, texto = 'Testando', testadas, teste_total, 'sites testados'
    else:
        rotulo, feitos, total, texto = 'Casas', foto.concluidas, foto.total_casas, 'concluídas'
    barra = Table.grid(padding=(0, 2))
    barra.add_row(
        ProgressBar(total=max(total, 1), completed=feitos, width=LARGURA_BARRA),
        Text(f'{feitos} de {total} {texto} ({_por_cento(feitos, total)})'),
    )
    blocos.add_row(rotulo, barra)
    restante = texto_restante(foto.restante)
    tempo = _duracao(foto.decorrido)
    blocos.add_row(
        'Tempo', Text(f'{tempo} · faltam {restante}' if foto.restante else f'{tempo} · {restante}')
    )
    partes.append(blocos)

    if foto.contagens:
        contagens = Table.grid(padding=(0, 1))
        contagens.add_column(width=LARGURA_ROTULO, style='bold')
        contagens.add_column()
        for rotulo_contagem, texto_contagem in foto.contagens:
            contagens.add_row(rotulo_contagem, texto_contagem)
        partes += [Text(''), contagens]

    if foto.em_andamento:
        casas = Table.grid(padding=(0, 2))
        casas.add_column()
        casas.add_column()
        casas.add_column(justify='right')
        casas.add_column()
        for host, etapa, feitos_casa, total_casa in foto.em_andamento:
            if total_casa:
                contagem = f'{feitos_casa}/{total_casa}'
                barra_casa: Any = ProgressBar(
                    total=total_casa, completed=feitos_casa, width=LARGURA_BARRA_CASA
                )
            else:
                contagem, barra_casa = '', Text('')
            casas.add_row(Text(f'  {host}'), Text(etapa), Text(contagem), barra_casa)
        titulo_casas = Text(f'Em andamento ({len(foto.em_andamento)})', style='bold')
        partes += [Text(''), titulo_casas, casas]
    return Group(*partes)


class Tela:
    """Onde o andamento e o resumo aparecem.

    `ao_vivo` (modo menus): linhas do log pelo console do `rich`, um painel
    que se atualiza durante a execução e o resumo num quadro. Senão (modo
    texto): o terminal de sempre (`registro.configurar` sem `terminal`), a
    linha de progresso a cada minuto e o resumo como texto.
    """

    def __init__(self, ao_vivo: bool = False, console: Any = None) -> None:
        self.ao_vivo = ao_vivo
        if ao_vivo and console is None:
            from rich.console import Console

            console = Console()
        self.console = console
        self._terminal = HandlerTerminal(console) if ao_vivo else None

    def terminal(self) -> logging.Handler | None:
        """O destino do terminal para `registro.configurar` (None = o padrão)."""
        return self._terminal

    @contextmanager
    def acompanhar(
        self, contagens: Callable[[], list[tuple[str, str]]] = lambda: [], titulo: str = ''
    ) -> Iterator[Andamento]:
        """Liga o `Andamento` ao log e, no modo ao vivo, mostra o painel durante o bloco."""
        with acompanhar(contagens, titulo) as andamento:
            if not self.ao_vivo:
                yield andamento
                return
            from rich.live import Live

            live = Live(
                get_renderable=lambda: painel(andamento.foto()),
                console=self.console,
                refresh_per_second=2,
                transient=True,
            )
            assert self._terminal is not None
            self._terminal.painel_ligado = True
            live.start()
            try:
                yield andamento
            finally:  # também no Ctrl+C
                live.stop()
                self._terminal.painel_ligado = False

    def resumo(self, texto: str) -> None:
        """O resumo vai para o log e aparece no terminal (num quadro, no modo ao vivo)."""
        log = registro.logger()
        if not self.ao_vivo:
            log.info(texto)
            return
        from rich.panel import Panel
        from rich.text import Text

        log.info(texto, extra={SO_ARQUIVO: True})
        self.console.print(Panel(Text(texto.strip('\n')), expand=False))
