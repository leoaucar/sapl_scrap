"""Casas legislativas: teste das URLs, UF, filtro Sul/Sudeste e limite."""

import pandas as pd
import pytest
import requests

from sapyl import casas as cl
from sapyl.cliente_http import ClienteSAPL


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


def test_importar_casas_da_planilha(projeto_tmp):
    casas = cl.importar_casas(projeto_tmp / 'arquivos_csv' / 'casas_legislativas.xlsx')
    assert list(casas.columns) == ['url', 'uf']
    assert list(casas['uf']) == ['AC', 'PR', 'SP']
    assert all(u.endswith('/') for u in casas['url'])


def test_casa_com_falha_fica_na_lista_com_motivo(cliente, sessao):
    casas = pd.DataFrame(
        {'url': ['https://a/', 'https://b/', 'https://c/'], 'uf': ['AC', 'PR', 'SP']}
    )
    sessao.responder('https://a/', texto='ok')
    sessao.responder('https://b/', erro=requests.ConnectionError())
    sessao.responder('https://c/', status=500)
    resultado = cl.testar_casas(casas, cliente)
    assert list(resultado.columns) == cl.COLUNAS_CASAS
    assert list(resultado['ativa']) == [True, False, False]
    assert list(resultado['motivo']) == ['', 'conexao', 'HTTP 500']
    assert list(resultado['uf']) == ['AC', 'PR', 'SP']
    # teste rápido: no máximo 2 tentativas e timeout curto
    assert sessao.contar('https://b/') == 2
    assert sessao.chamadas[0][1]['timeout'] == (5, 5)


def test_tabela_antiga_lida_com_uf_da_planilha(projeto_tmp):
    antiga = projeto_tmp / 'casas_resultado.csv'
    antiga.write_text(
        '0,1\nhttps://sapl.a.ac.leg.br/,True\nhttps://sapl.b.pr.leg.br,False\n'
        'https://sapl.c.sp.leg.br/,True\n',
        encoding='utf-8',
    )
    casas = cl.ler_tabela_casas(antiga, projeto_tmp / 'arquivos_csv' / 'casas_legislativas.xlsx')
    assert list(casas.columns) == cl.COLUNAS_CASAS
    assert list(casas['url'])[1] == 'https://sapl.b.pr.leg.br/'
    assert list(casas['ativa']) == [True, False, True]
    assert list(casas['uf']) == ['AC', 'PR', 'SP']


def test_tabela_nova_ida_e_volta(tmp_path):
    casas = pd.DataFrame(
        {'url': ['https://a/'], 'ativa': [False], 'motivo': ['timeout'], 'uf': ['RS']}
    )
    cl.salvar_tabela_casas(casas, tmp_path / 't.csv')
    lida = cl.ler_tabela_casas(tmp_path / 't.csv')
    assert lida.to_dict('records') == [
        {'url': 'https://a/', 'ativa': False, 'motivo': 'timeout', 'uf': 'RS', 'url_final': ''}
    ]


def test_sul_sudeste_aplicado_em_tabela_reaproveitada(projeto_tmp):
    antiga = projeto_tmp / 'casas_resultado.csv'
    antiga.write_text(
        '0,1\nhttps://sapl.a.ac.leg.br/,True\nhttps://sapl.b.pr.leg.br/,True\n'
        'https://sapl.c.sp.leg.br/,True\n',
        encoding='utf-8',
    )
    casas = cl.ler_tabela_casas(antiga, projeto_tmp / 'arquivos_csv' / 'casas_legislativas.xlsx')
    assert list(cl.filtrar_estados(casas, cl.ESTADOS_SUL_SUDESTE)['uf']) == ['PR', 'SP']


def test_limites():
    casas = pd.DataFrame({'url': [f'https://{i}/' for i in range(120)], 'uf': ['SP'] * 120})
    assert len(cl.limitar_casas(casas, '1')) == 120
    assert list(cl.limitar_casas(casas, '2')['url'])[-1] == 'https://49/'
    ultimas = cl.limitar_casas(casas, '3')
    assert len(ultimas) == 50 and list(ultimas['url'])[0] == 'https://70/'
    assert len(cl.limitar_casas(casas, 4)) == 10
    with pytest.raises(ValueError):
        cl.limitar_casas(casas, '5')


def test_planilha_ausente_ou_sem_colunas_vira_entrada_invalida(tmp_path):
    from sapyl.padroes import EntradaInvalida

    with pytest.raises(EntradaInvalida, match='Não encontrei a planilha'):
        cl.importar_casas(tmp_path / 'casas_legislativas.xlsx')
    pd.DataFrame({'Estado': ['AC']}).to_excel(tmp_path / 'c.xlsx', index=False)
    with pytest.raises(EntradaInvalida, match='UF, URL do serviço'):
        cl.importar_casas(tmp_path / 'c.xlsx')
    (tmp_path / 'ruim.xlsx').write_text('x')
    with pytest.raises(EntradaInvalida, match='Não consegui ler'):
        cl.importar_casas(tmp_path / 'ruim.xlsx')


def test_ufs_e_filtrar_estados():
    casas = pd.DataFrame(
        {
            'url': ['https://a/', 'https://b/', 'https://c/', 'https://d/'],
            'uf': ['SP', 'AC', 'SP', ''],
        }
    )
    assert cl.ufs(casas) == ['AC', 'SP']
    assert list(cl.filtrar_estados(casas, ['sp'])['url']) == ['https://a/', 'https://c/']
    assert len(cl.filtrar_estados(casas, [])) == 4
    assert list(cl.filtrar_estados(casas, cl.ESTADOS_SUL_SUDESTE)['uf']) == ['SP', 'SP']


def test_limite_de_teste_e_limites_antigos():
    casas = pd.DataFrame({'url': [f'https://{i}/' for i in range(60)], 'uf': ['SP'] * 60})
    assert len(cl.limitar_casas(casas, cl.LIMITE_TESTE)) == cl.CASAS_NO_TESTE
    assert len(cl.limitar_casas(casas, cl.LIMITE_TODAS)) == 60
    assert cl.limitar_casas(casas, '3')['url'].iloc[0] == 'https://10/'
    assert len(cl.limitar_casas(casas, '2')) == 50


def test_teste_das_casas_nao_avisa_falhas_no_terminal(cliente, sessao, caplog):
    import logging

    sessao.responder('https://b/', status=500)
    casas = pd.DataFrame({'url': ['https://b/'], 'uf': ['PR']})
    with caplog.at_level(logging.DEBUG, logger='sapyl'):
        cl.testar_casas(casas, cliente)
    falhas = [r for r in caplog.records if r.getMessage().startswith('Falha em')]
    assert falhas and all(r.levelno == logging.DEBUG for r in falhas)
