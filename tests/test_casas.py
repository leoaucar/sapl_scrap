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
    assert list(cl.filtrar_sul_sudeste(casas)['uf']) == ['PR', 'SP']


def test_limites():
    casas = pd.DataFrame({'url': [f'https://{i}/' for i in range(120)], 'uf': ['SP'] * 120})
    assert len(cl.limitar_casas(casas, '1')) == 120
    assert list(cl.limitar_casas(casas, '2')['url'])[-1] == 'https://49/'
    ultimas = cl.limitar_casas(casas, '3')
    assert len(ultimas) == 50 and list(ultimas['url'])[0] == 'https://70/'
    assert len(cl.limitar_casas(casas, 4)) == 10
    with pytest.raises(ValueError):
        cl.limitar_casas(casas, '5')


def test_pergunta_de_limite_lista_as_quatro_opcoes():
    for opcao in ('1-', '2-', '3-', '4-'):
        assert opcao in cl.PERGUNTA_LIMITE
    assert '5-' not in cl.PERGUNTA_LIMITE


def test_teste_em_paralelo_da_a_mesma_tabela_na_ordem(cliente, sessao):
    """FR-3: várias casas ao mesmo tempo, o mesmo resultado de uma por vez."""
    from sapyl import execucao
    from tests.test_cliente_http import _erro_dns

    urls = [f'https://sapl.c{i}.leg.br/' for i in range(20)]
    for i, url in enumerate(urls):
        if i % 5 == 1:
            sessao.responder(url, erro=_erro_dns())
        elif i % 5 == 3:
            sessao.responder(url, status=503)
        else:
            sessao.responder(url, texto='ok', url_final=url if i % 7 else f'https://novo{i}.br/')
    casas = pd.DataFrame({'url': urls, 'uf': ['AC'] * 20})
    sequencial = cl.testar_casas(casas, cliente)
    pedidos = len(sessao.pedidos)

    def mapear(tarefa, itens):
        return execucao.por_casa(itens, tarefa, 8, cliente.parar)

    paralelo = cl.testar_casas(casas, cliente, mapear)
    assert paralelo.equals(sequencial)
    assert list(paralelo['url']) == urls
    assert paralelo.at[1, 'motivo'] == 'dns' and paralelo.at[3, 'motivo'] == 'HTTP 503'
    assert paralelo.at[0, 'url_final'] == 'https://novo0.br/'
    assert len(sessao.pedidos) - pedidos == pedidos  # mesmas requisições
    assert sessao.contar(urls[1]) == 2  # nome inexistente: uma tentativa em cada teste
