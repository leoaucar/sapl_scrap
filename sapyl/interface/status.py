"""Andamento da execução: o que cada casa está fazendo, contagens e tempo restante.

As camadas de baixo só escrevem no log (veja `registro.andamento` e
`execucao.por_casa`). `HandlerAndamento` lê esses registros e atualiza um
`Andamento`, que a interface mostra: numa linha a cada minuto (modo texto)
ou num painel ao vivo (modo menus, veja `PainelAoVivo`).

Tempo restante (estimativa): só depois de 1 minuto e de pelo menos uma casa
concluída. Trabalho que falta = matérias conhecidas e ainda não raspadas (das
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

    def texto_da_etapa(self) -> str:
        """`matérias 45/120`, `buscando 2/3`, ou `começando`."""
        if not self.etapa:
            return 'começando'
        nome = NOMES_DAS_ETAPAS.get(self.etapa, self.etapa)
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
    em_andamento: list[tuple[str, str]]  # (host, etapa)
    teste: tuple[int, int]  # casas testadas, total
    decorrido: float
    restante: float | None
    contagens: str


@dataclass
class Andamento:
    """Estado do andamento, alimentado pelos registros do log (seguro entre threads).

    `contagens`: texto das contagens do projeto todo (do arquivo de estado),
    para a retomada mostrar o total e não só o desta execução.
    """

    contagens: Callable[[], str] = lambda: ''
    relogio: Callable[[], float] = time.monotonic
    total_casas: int = 0
    casas: dict[str, Casa] = field(default_factory=dict)
    concluidas: dict[str, Casa] = field(default_factory=dict)
    teste_feitos: int = 0
    teste_total: int = 0

    def __post_init__(self) -> None:
        self._trava = threading.Lock()
        self.inicio = self.relogio()
        self._feitas: deque[tuple[float, int]] = deque()
        self._total_feitas = 0

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
            self._total_feitas += 1
            self._feitas.append((self.relogio(), self._total_feitas))
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
        janela = min(JANELA_RITMO, agora - self.inicio)
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

    def foto(self) -> Foto:
        """O andamento agora (para o painel ou a linha)."""
        restante = self.restante()
        with self._trava:
            return Foto(
                # sem `comecar` (autoria), o total é o que já apareceu
                total_casas=max(self.total_casas, len(self.casas) + len(self.concluidas)),
                concluidas=len(self.concluidas),
                em_andamento=[(h, c.texto_da_etapa()) for h, c in self.casas.items()],
                teste=(self.teste_feitos, self.teste_total),
                decorrido=self.relogio() - self.inicio,
                restante=restante,
                contagens=self.contagens(),
            )

    def progresso(self) -> str:
        """Fim da linha de progresso do modo texto: contagens e tempo restante."""
        foto = self.foto()
        partes = [foto.contagens] if foto.contagens else []
        partes.append(f'tempo restante: {texto_restante(foto.restante)}')
        return '; '.join(partes)


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
def acompanhar(contagens: Callable[[], str] = lambda: '') -> Iterator[Andamento]:
    """Liga um `Andamento` ao log do programa durante o bloco."""
    andamento = Andamento(contagens)
    handler = HandlerAndamento(andamento)
    logger = registro.logger()
    if logger.level == logging.NOTSET:  # sem `registro.configurar` (testes)
        logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        yield andamento
    finally:
        logger.removeHandler(handler)
