"""Registro da execução (log) e resumo final.

Todas as mensagens passam pelo logger `sapyl`:
- no terminal, nível INFO (progresso e avisos);
- no arquivo `<pasta>/<nome>.log`, nível DEBUG (inclui uma linha por
  requisição HTTP, usada para conferir o limite de requisições).
"""

import logging
import os
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from sapyl import __version__
from sapyl.colunas import ETAPA_MATERIA, ETAPA_PDF, SEPARADOR, Linha

LOGGER = 'sapyl'
NOME = 'SAPyL: Raspador do Sistema de Apoio Legislativo'
FORMATO_ARQUIVO = '%(asctime)s %(levelname)s %(name)s %(message)s'

# Marca os handlers criados aqui, para `configurar` poder ser chamada de novo
_MARCA = '_sapyl'


class _Contagens(Protocol):
    """O que o resumo usa do estado do projeto (`sapyl.estado.Estado`)."""

    def contagens(self, etapa: str, chaves: Iterable[str] | None = None) -> Counter[str]: ...


def configurar(pasta: str | Path, nome: str) -> str:
    """Liga o log no terminal e em `<pasta>/<nome>.log`. Pode ser chamada várias vezes."""
    logger = logging.getLogger(LOGGER)
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        if getattr(handler, _MARCA, False):
            logger.removeHandler(handler)
            handler.close()

    terminal = logging.StreamHandler()
    terminal.setLevel(logging.INFO)
    terminal.setFormatter(logging.Formatter('%(message)s'))

    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome + '.log')
    arquivo = logging.FileHandler(caminho, encoding='utf-8')
    arquivo.setLevel(logging.DEBUG)
    arquivo.setFormatter(logging.Formatter(FORMATO_ARQUIVO))

    for handler in (terminal, arquivo):
        setattr(handler, _MARCA, True)
        logger.addHandler(handler)
    # Cabeçalho, só no arquivo: cada execução começa com o nome e a versão
    logger.debug('%s %s: início da execução', NOME, __version__)
    return caminho


def logger(nome: str | None = None) -> logging.Logger:
    """Logger de um módulo: `sapyl` ou `sapyl.<nome>`."""
    return logging.getLogger(LOGGER if not nome else f'{LOGGER}.{nome}')


def resumo(
    estado: _Contagens,
    links: list[Linha],
    caminho_final: str | Path,
    buscas: list[tuple[str, str]] | None = None,
    casas_inativas: int = 0,
    downloads: bool = False,
) -> str:
    """Texto do resumo do fim da execução, contado a partir do estado do projeto.

    `buscas`: lista de (casa, status) das buscas do projeto (None no modo
    atualização, que não faz buscas). Como tudo vem do estado, o resumo é o
    do projeto inteiro, também depois de uma retomada.
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
    linhas.append(f'Resultado: {caminho_final}')
    if falhas:
        linhas.append(
            'Houve falhas (veja as colunas status/erro e o arquivo .log). '
            'Para tentar de novo só o que falhou, rode o programa outra vez '
            'e escolha retomar este projeto.'
        )
    return '\n'.join(linhas)
