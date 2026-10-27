"""Projetos feitos com a versão da Fase 1 continuam funcionando (TR-4).

A pasta tests/fixtures/projeto_fase1/fase1_proj/ foi gravada pelo código da
Fase 1 (veja tests/fixtures/gerar_projeto_fase1.py). Cada teste trabalha numa
cópia, para a fixture nunca mudar.
"""

import shutil

import pytest

from sapyl.cliente_http import ClienteSAPL
from sapyl.interface import principal as programa
from sapyl.links import raspar_resultados
from sapyl.tabela import ler_final
from tests.apoio import FALHA_FASE1, PASTA_FIXTURES, RelogioFalso, SessaoFalsa, roteiro, sapl_fase1

ORIGEM = PASTA_FIXTURES / 'projeto_fase1' / 'fase1_proj'
ARQUIVOS = [
    'config.json',
    'casas_resultado.csv',
    'fase1_estado.csv',
    'fase1_resultados_crus_casas.csv',
    'fase1_links_totais.csv',
    'fase1_materias_legislativas.csv',
    'fase1_resultado_final.csv',
    'fase1.log',
]


@pytest.fixture
def copia(tmp_path):
    shutil.copytree(ORIGEM, tmp_path / 'fase1_proj')
    return tmp_path


def _cliente():
    sessao, relogio = SessaoFalsa(), RelogioFalso()
    sessao.rota(sapl_fase1(falhar=False))
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir), sessao


def test_fixture_tem_os_arquivos_da_fase1():
    for nome in ARQUIVOS:
        assert (ORIGEM / nome).is_file(), nome
    assert len(list((ORIGEM / 'downloads').glob('*.pdf'))) == 3
    final = ler_final(ORIGEM / 'fase1_resultado_final.csv')
    assert len(final) == 8
    assert final.loc[final['status'] == 'erro', 'sapl_id'].tolist() == ['44086']
    assert len(raspar_resultados(ORIGEM / 'fase1_resultados_crus_casas.csv')) == 8


def test_retomada_so_pede_o_que_falhou(copia):
    cliente, sessao = _cliente()
    assert programa.main(roteiro('2', 'fase1', '1'), cliente, copia) == 0
    assert not any('/sistema/search/' in u for u in sessao.pedidos)
    materias = [
        u
        for u in sessao.pedidos
        if '/media/' not in u
        and ('/api/materia/materialegislativa/' in u or '/api/' not in u and '/materia/' in u)
    ]
    assert materias == [FALHA_FASE1]
    # os PDFs já baixados não são pedidos de novo
    assert not any(
        '/media/' in u and ('34049' in u or '46496' in u or '38415' in u) for u in sessao.pedidos
    )
    final = ler_final(copia / 'fase1_proj' / 'fase1_resultado_final.csv')
    assert set(final['status']) == {'ok'} and len(final) == 8
