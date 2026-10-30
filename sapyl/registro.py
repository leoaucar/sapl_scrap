"""Registro da execução (log) e resumo final.

Todas as mensagens passam pelo logger `sapyl`:
- no terminal, nível INFO (progresso e avisos);
- num arquivo por execução, `<pasta>/logs/<nome>_<aaaa-mm-dd_hhmmss>_<modo>.log`,
  nível DEBUG (inclui uma linha por requisição HTTP, usada para conferir o
  limite de requisições). O `<nome>.log` de projetos antigos fica como está.

Com várias casas ao mesmo tempo, cada linha escrita durante o trabalho de uma
casa começa com `[<host>] ` (veja `casa_atual`). As linhas de requisição
(`sapyl.http`) não ganham o prefixo: já começam pelo host, e o formato delas é
o que os scripts de validação leem.
"""

import logging
import os
import threading
from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Protocol

from sapyl import __version__
from sapyl.colunas import ETAPA_MATERIA, ETAPA_PDF, SEPARADOR, Linha

LOGGER = 'sapyl'
NOME = 'SAPyL: Raspador do Sistema de Apoio Legislativo'
FORMATO_ARQUIVO = '%(asctime)s %(levelname)s %(name)s %(casa)s%(message)s'
FORMATO_TERMINAL = '%(casa)s%(message)s'

# Casa em que a thread atual está trabalhando (para o prefixo das linhas)
_contexto = threading.local()

# Marca os handlers criados aqui, para `configurar` poder ser chamada de novo
_MARCA = '_sapyl'

# Modos de execução, que vão no nome do arquivo de log
MODOS = ('novo', 'retomada', 'atualizacao', 'autoria')

# Arquivo de log da execução atual (o resumo mostra o caminho)
_log_atual: str | None = None


class _Contagens(Protocol):
    """O que o resumo usa do estado do projeto (`sapyl.estado.Estado`)."""

    def contagens(self, etapa: str, chaves: Iterable[str] | None = None) -> Counter[str]: ...


@contextmanager
def casa_atual(host: str) -> Iterator[None]:
    """Durante o bloco, as linhas do log desta thread começam com `[<host>] `."""
    anterior = getattr(_contexto, 'casa', '')
    _contexto.casa = host
    try:
        yield
    finally:
        _contexto.casa = anterior


class _PrefixoCasa(logging.Filter):
    """Preenche `%(casa)s` com `[<host>] ` (ou vazio) para os formatos daqui."""

    def filter(self, record: logging.LogRecord) -> bool:
        casa = getattr(_contexto, 'casa', '')
        http = record.name == f'{LOGGER}.http'
        record.casa = f'[{casa}] ' if casa and not http else ''
        return True


def caminho_do_log(pasta: str | Path, nome: str, modo: str, agora: datetime | None = None) -> Path:
    """`<pasta>/logs/<nome>_<aaaa-mm-dd_hhmmss>_<modo>.log`, sem repetir um arquivo existente."""
    if modo not in MODOS:
        raise ValueError(f'Modo de execução desconhecido: {modo}')
    base = f'{nome}_{(agora or datetime.now()).strftime("%Y-%m-%d_%H%M%S")}_{modo}'
    pasta_logs = Path(pasta) / 'logs'
    caminho, n = pasta_logs / f'{base}.log', 1
    while caminho.exists():
        n += 1
        caminho = pasta_logs / f'{base}_{n}.log'
    return caminho


def configurar(
    pasta: str | Path, nome: str, modo: str = 'novo', agora: datetime | None = None
) -> str:
    """Liga o log no terminal e num arquivo novo em `<pasta>/logs/`. Devolve o caminho.

    Pode ser chamada várias vezes: troca os destinos anteriores pelos novos.
    """
    global _log_atual
    logger = logging.getLogger(LOGGER)
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        if getattr(handler, _MARCA, False):
            logger.removeHandler(handler)
            handler.close()

    terminal = logging.StreamHandler()
    terminal.setLevel(logging.INFO)
    terminal.setFormatter(logging.Formatter(FORMATO_TERMINAL))

    caminho = str(caminho_do_log(pasta, nome, modo, agora))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    arquivo = logging.FileHandler(caminho, encoding='utf-8')
    arquivo.setLevel(logging.DEBUG)
    arquivo.setFormatter(logging.Formatter(FORMATO_ARQUIVO))

    for handler in (terminal, arquivo):
        setattr(handler, _MARCA, True)
        handler.addFilter(_PrefixoCasa())
        logger.addHandler(handler)
    # Cabeçalho, só no arquivo: cada execução começa com o nome e a versão
    logger.debug('%s %s: início da execução (%s)', NOME, __version__, modo)
    _log_atual = caminho
    return caminho


def logger(nome: str | None = None) -> logging.Logger:
    """Logger de um módulo: `sapyl` ou `sapyl.<nome>`."""
    return logging.getLogger(LOGGER if not nome else f'{LOGGER}.{nome}')


def formatar_duracao(segundos: float) -> str:
    """`3725.4` -> `1 h 02 min 05 s`; `65` -> `1 min 05 s`; `7` -> `7 s`."""
    total = int(round(segundos))
    horas, resto = divmod(total, 3600)
    minutos, seg = divmod(resto, 60)
    if horas:
        return f'{horas} h {minutos:02d} min {seg:02d} s'
    if minutos:
        return f'{minutos} min {seg:02d} s'
    return f'{seg} s'


def linhas_da_execucao(
    duracao: float,
    casas_ao_mesmo_tempo: int,
    servidores: Iterable[tuple[str, int, int, int]] = (),
) -> list[str]:
    """Linhas do resumo sobre a execução: tempo, casas ao mesmo tempo e servidores.

    `servidores`: (servidor, nº de casas, limite inicial, limite no fim), por
    requisições por minuto.
    """
    linhas = [
        f'Tempo: {formatar_duracao(duracao)} (até {casas_ao_mesmo_tempo} casas ao mesmo tempo)'
    ]
    for servidor, casas, inicial, final in servidores:
        texto = f'Servidor {servidor} ({casas} casa{"s" if casas != 1 else ""}): '
        if final < inicial:
            texto += (
                f'limite reduzido de {inicial} para {final} requisições por minuto '
                '(429 de mais de uma casa)'
            )
        else:
            texto += f'até {inicial} requisições por minuto'
        linhas.append(texto)
    return linhas


def resumo_autoria(
    contagens: Counter[str],
    saida: str | Path,
    caminho_log: str | None = None,
    execucao: list[str] | None = None,
) -> str:
    """Texto do resumo da autoria e tramitação (`execucao`: veja `linhas_da_execucao`)."""
    total = sum(contagens.values())
    linhas = [
        '',
        f'===== Resumo (SAPyL {__version__}) =====',
        f'Autoria e tramitação: {total} matérias, {contagens.get("ok", 0)} ok, '
        f'{contagens.get("erro", 0)} com erro',
        *(execucao or []),
        f'Resultado: {saida}',
    ]
    if contagens.get('erro', 0):
        linhas.append(
            'Houve falhas (veja as colunas status_autoria/status_tramitacao). Para tentar de '
            'novo só o que falhou, rode o programa outra vez, escolha 3 e a mesma entrada.'
        )
    caminho_log = caminho_log or _log_atual
    if caminho_log:
        linhas.append(f'Log desta execução: {caminho_log}')
    return '\n'.join(linhas)


def resumo(
    estado: _Contagens,
    links: list[Linha],
    caminho_final: str | Path,
    buscas: list[tuple[str, str]] | None = None,
    casas_inativas: int = 0,
    downloads: bool = False,
    caminho_log: str | None = None,
    execucao: list[str] | None = None,
) -> str:
    """Texto do resumo do fim da execução, contado a partir do estado do projeto.

    `buscas`: lista de (casa, status) das buscas do projeto (None no modo
    atualização, que não faz buscas). Como tudo vem do estado, o resumo é o
    do projeto inteiro, também depois de uma retomada. A última linha mostra
    o log desta execução (`caminho_log`, ou o da última `configurar`).
    `execucao`: linhas sobre tempo e servidores (veja `linhas_da_execucao`).
    """
    chaves = {link['chave'] for link in links}
    linhas = ['', f'===== Resumo (SAPyL {__version__}) =====']
    falhas = False
    if buscas is not None:
        casas = {casa for casa, _ in buscas}
        incompletas = [(casa, st) for casa, st in buscas if st != 'completa']
        casas_falha = {casa for casa, _ in incompletas}
        linhas.append(
            f'Casas pesquisadas: {len(casas)} '
            f'({len(casas_falha)} com alguma busca incompleta; '
            f'{casas_inativas} fora do ar, não pesquisadas)'
        )
        linhas.append(f'Buscas: {len(buscas)} ({len(incompletas)} incompletas)')
        falhas = falhas or bool(incompletas)
    encontradas = sum(len([p for p in link['Palavras'].split(SEPARADOR) if p]) for link in links)
    materias = estado.contagens(ETAPA_MATERIA, chaves)
    linhas.append(
        f'Matérias: {encontradas} encontradas, {len(chaves)} únicas, '
        f'{materias.get("ok", 0)} raspadas, {materias.get("erro", 0)} com erro'
    )
    falhas = falhas or materias.get('erro', 0) > 0
    if downloads:
        pdfs = estado.contagens(ETAPA_PDF, chaves)
        linhas.append(
            f'Downloads: {pdfs.get("ok", 0)} baixados, {pdfs.get("erro", 0)} com erro, '
            f'{pdfs.get("sem_pdf", 0)} sem texto original'
        )
        falhas = falhas or pdfs.get('erro', 0) > 0
    linhas += execucao or []
    linhas.append(f'Resultado: {caminho_final}')
    if falhas:
        linhas.append(
            'Houve falhas (veja as colunas status/erro e o log desta execução). '
            'Para tentar de novo só o que falhou, rode o programa outra vez '
            'e escolha retomar este projeto.'
        )
    caminho_log = caminho_log or _log_atual
    if caminho_log:
        linhas.append(f'Log desta execução: {caminho_log}')
    return '\n'.join(linhas)
