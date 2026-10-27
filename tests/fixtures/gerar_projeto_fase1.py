"""Gera tests/fixtures/projeto_fase1/ com o código da Fase 1 (registro histórico).

Rodado uma vez, em 27/10/2026, antes de o código virar o pacote `sapyl`
(spec 2026-10-24-organizacao-e-pendencias, T01). Depois da mudança, os
módulos importados aqui não existem mais com estes nomes; o script fica
só para documentar como a pasta foi feita.

Uso (na raiz do repositório, com o código da Fase 1):
    .venv/bin/python -m tests.fixtures.gerar_projeto_fase1

Projeto "fase1": 2 casas do SAPL falso (`tests.apoio.sapl_fase1`), as duas
palavras de `PALAVRAS_FASE1`, sem filtro, todas as casas, com downloads. A
matéria 44086 fica com `erro` (HTTP 503). A execução roda numa pasta
temporária com caminhos relativos, para nenhum caminho da máquina ir parar
nos arquivos gravados.
"""
import os
import shutil
import socket
import tempfile
from pathlib import Path

import pandas as pd

import programa
from http_sapl import ClienteSAPL
from tests.apoio import (CV_FASE1, PALAVRAS_FASE1, RB_FASE1, RelogioFalso, SessaoFalsa,
                         roteiro, sapl_fase1)

DESTINO = Path(__file__).resolve().parent / 'projeto_fase1'
RESPOSTAS = ('2', 'fase1', '2', '1', '1')   # novo, nome, sem filtro, todas, com downloads


def _sem_rede(*args, **kwargs):
    raise RuntimeError('o gerador não acessa a rede')


def gerar():
    socket.socket.connect = _sem_rede
    origem = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            Path('arquivos_csv').mkdir()
            pd.DataFrame({'UF': ['AC', 'PR'], 'URL do serviço': [RB_FASE1, CV_FASE1]}).to_excel(
                'arquivos_csv/casas_legislativas.xlsx', index=False)
            pd.DataFrame({'Palavras': PALAVRAS_FASE1}).to_excel(
                'arquivos_csv/palavras_chave.xlsx', index=False)
            sessao, relogio = SessaoFalsa(), RelogioFalso()
            sessao.rota(sapl_fase1())
            cliente = ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)
            assert programa.main(roteiro(*RESPOSTAS), cliente, '.') == 0
            shutil.rmtree(DESTINO, ignore_errors=True)
            shutil.copytree('fase1_proj', DESTINO / 'fase1_proj')
        finally:
            os.chdir(origem)
    print(f'Gravado em {DESTINO}')


if __name__ == '__main__':
    gerar()
