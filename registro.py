"""Registro da execução (log) e resumo final.

Todas as mensagens passam pelo logger `sapl_scrap`:
- no terminal, nível INFO (progresso e avisos);
- no arquivo `<pasta>/<nome>.log`, nível DEBUG (inclui uma linha por
  requisição HTTP, usada para conferir o limite de requisições).
"""
import logging
import os

LOGGER = 'sapl_scrap'
FORMATO_ARQUIVO = '%(asctime)s %(levelname)s %(name)s %(message)s'

# Marca os handlers criados aqui, para `configurar` poder ser chamada de novo
_MARCA = '_sapl_scrap'


def configurar(pasta, nome):
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
    return caminho


def logger(nome=None):
    """Logger de um módulo: `sapl_scrap` ou `sapl_scrap.<nome>`."""
    return logging.getLogger(LOGGER if not nome else f'{LOGGER}.{nome}')
