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
from tests.apoio import (
    FALHA_FASE1,
    PASTA_FIXTURES,
    RelogioFalso,
    SessaoFalsa,
    respostas_atualizar,
    respostas_autoria,
    respostas_retomar,
    roteiro,
    sapl_fase1,
)

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
    assert programa.main(roteiro(*respostas_retomar()), cliente, copia) == 0
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
    # o log antigo fica como estava; a retomada ganha o seu próprio arquivo
    antigo = (ORIGEM / 'fase1.log').read_text(encoding='utf-8')
    assert (copia / 'fase1_proj' / 'fase1.log').read_text(encoding='utf-8') == antigo
    logs = list((copia / 'fase1_proj' / 'logs').glob('fase1_*_retomada.log'))
    assert len(logs) == 1


def test_busca_incompleta_de_projeto_antigo_usa_os_dois_arquivos(copia):
    pasta = copia / 'fase1_proj'
    cru = (pasta / 'fase1_resultados_crus_casas.csv').read_bytes()
    # uma das buscas de Cascavel ficou incompleta na Fase 1
    with open(pasta / 'fase1_estado.csv', 'a', encoding='utf-8', newline='') as estado:
        estado.write('busca,"sapl.cascavel.pr.leg.br|""plano+diretor""",incompleta,x,27/10/2026\n')
    cliente, sessao = _cliente()
    assert programa.main(roteiro(*respostas_retomar()), cliente, copia) == 0
    buscas = [u for u in sessao.pedidos if '/sistema/search/' in u]
    assert buscas and all('sapl.cascavel.pr.leg.br' in u and 'plano+diretor' in u for u in buscas)
    # o arquivo antigo não é escrito; a busca refeita vai para o arquivo novo
    assert (pasta / 'fase1_resultados_crus_casas.csv').read_bytes() == cru
    assert (pasta / 'fase1_paginas_busca.csv').exists()
    final = ler_final(pasta / 'fase1_resultado_final.csv')
    assert len(final) == 8 and final['sapl_id'].is_unique


def test_atualizacao_de_projeto_antigo(copia):
    cliente, sessao = _cliente()
    assert programa.main(roteiro(*respostas_atualizar('n')), cliente, copia) == 0
    pasta = copia / 'fase1_proj'
    [arquivo] = pasta.glob('fase1_resultado_final_ATUALIZADO_*.csv')
    final = ler_final(arquivo)
    assert len(final) == 8 and set(final['status']) == {'ok'}
    assert not any('/sistema/search/' in u for u in sessao.pedidos)
    # a tabela de casas da Fase 1 (sem url_final) continua valendo
    assert all(
        u.startswith(('https://sapl.riobranco', 'https://sapl.cascavel')) for u in sessao.pedidos
    )


def test_autoria_de_projeto_antigo(copia):
    cliente, sessao = _cliente()
    assert programa.main(roteiro(*respostas_autoria()), cliente, copia) == 0
    saida = copia / 'fase1_proj' / 'fase1_resultado_final_autoria_tramitacao.csv'
    tabela = ler_final(saida)
    assert len(tabela) == 8
    assert set(tabela['fonte_autoria']) <= {'api', 'html'}
