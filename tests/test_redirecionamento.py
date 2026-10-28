"""Casas cujo site redireciona para outro domínio (FR-27)."""

import pandas as pd
import pytest

from sapyl import busca
from sapyl import casas as cl
from sapyl import materias as m
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import COLUNAS_PAGINAS
from sapyl.estado import Cache, Estado, ler_csv
from sapyl.interface import principal as programa
from sapyl.links import base_da_casa, endereco_final, links_da_pagina, no_endereco, normalizar_link
from sapyl.tabela import ler_final
from tests.apoio import SaplFalso, roteiro
from tests.test_materias import _link, _responder_consultas

ANTIGO = 'https://sapl.antigo.ac.leg.br/'
NOVO = 'https://sapl.novo.ac.leg.br/'
RB = 'https://sapl.riobranco.ac.leg.br/'
P = '"plano+diretor"'


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


# --- Endereços ----------------------------------------------------------------


def test_endereco_final_so_quando_sai_da_casa():
    assert endereco_final(NOVO + 'qualquer/coisa', ANTIGO) == NOVO
    assert (
        endereco_final('http://sapl.antigo.ac.leg.br/', ANTIGO) == 'http://sapl.antigo.ac.leg.br/'
    )
    assert endereco_final(ANTIGO + 'pagina', ANTIGO) == ''
    assert endereco_final('', ANTIGO) == ''


def test_base_e_troca_de_endereco():
    finais = {'sapl.antigo.ac.leg.br': NOVO}
    assert base_da_casa(ANTIGO, finais) == NOVO
    assert base_da_casa(RB, finais) == RB
    assert no_endereco(ANTIGO + 'materia/7', ANTIGO, NOVO) == NOVO + 'materia/7'
    assert no_endereco('https://outro/x', ANTIGO, NOVO) == 'https://outro/x'
    assert no_endereco(RB + 'materia/7', RB, RB) == RB + 'materia/7'


def test_links_nos_dois_dominios_ficam_no_endereco_original():
    html = f'<a href="{NOVO}materia/7">a</a><a href="/materia/8">b</a><a href="https://x/materia/9">c</a>'
    assert links_da_pagina(html, ANTIGO, [NOVO]) == [ANTIGO + 'materia/7', ANTIGO + 'materia/8']
    assert normalizar_link(ANTIGO, NOVO + 'materia/7') is None  # sem o outro endereço, recusa


# --- Teste das casas e tabela -------------------------------------------------


def test_redirecionamento_grava_url_final(cliente, sessao):
    casas = pd.DataFrame({'url': [ANTIGO, RB], 'uf': ['AC', 'AC']})
    sessao.responder(ANTIGO, texto='início', url_final=NOVO)
    sessao.responder(RB, texto='início')
    resultado = cl.testar_casas(casas, cliente)
    assert list(resultado['url_final']) == [NOVO, '']
    assert cl.enderecos_finais(resultado) == {'sapl.antigo.ac.leg.br': NOVO}


def test_tabela_antiga_sem_url_final_continua_valendo(tmp_path):
    (tmp_path / 't.csv').write_text('url,ativa,motivo,uf\nhttps://a/,True,,RS\n', encoding='utf-8')
    lida = cl.ler_tabela_casas(tmp_path / 't.csv')
    assert lida.to_dict('records') == [
        {'url': 'https://a/', 'ativa': True, 'motivo': '', 'uf': 'RS', 'url_final': ''}
    ]
    assert cl.enderecos_finais(lida) == {}


# --- Requisições vão para o endereço novo ------------------------------------


def test_busca_pede_no_endereco_novo_e_grava_no_original(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [ANTIGO], 'ativa': [True], 'url_final': [NOVO]})
    sessao.responder(busca.url_busca(NOVO, P, 1), texto=f'<a href="{NOVO}materia/7">x</a>')
    sessao.responder(busca.url_busca(NOVO, P, 2), status=404)
    estado = Estado(tmp_path / 'e.csv')
    busca.buscar(casas, [P], cliente, estado, tmp_path / 'p.csv')
    assert all(u.startswith(NOVO) for u in sessao.pedidos)
    assert estado.status('busca', busca.chave_busca(ANTIGO, P)) == 'completa'
    [pagina] = ler_csv(tmp_path / 'p.csv', COLUNAS_PAGINAS)
    assert (pagina['Casa'], pagina['links']) == (ANTIGO, ANTIGO + 'materia/7')


def test_materia_pela_api_no_endereco_novo_com_chave_original(cliente, sessao):
    dados = {
        'id': 7,
        '__str__': 'Lei nº 1',
        'texto_original': 'http://sapl.novo.ac.leg.br/media/t.pdf',
    }
    sessao.responder(m.url_api(NOVO, '7'), json_dados=dados)
    linha = m.raspar_materia(
        _link(ANTIGO, '7'), cliente, m.Fontes(finais={'sapl.antigo.ac.leg.br': NOVO})
    )
    assert (linha['status'], linha['fonte'], linha['chave']) == (
        'ok',
        'api',
        'sapl.antigo.ac.leg.br/7',
    )
    assert linha['Link Materia'] == ANTIGO + 'materia/7' and linha['Link Casa'] == ANTIGO
    assert linha['texto_original'] == NOVO + 'media/t.pdf'
    assert sessao.pedidos == [m.url_api(NOVO, '7')]


def test_materia_pelo_html_no_endereco_novo(cliente, sessao):
    sessao.responder(m.url_api(NOVO, '43301'), status=404)
    sessao.responder(
        NOVO + 'materia/43301', fixture='sapl/sapl.cascavel.pr.leg.br/materia_43301.html'
    )
    linha = m.raspar_materia(
        _link(ANTIGO, '43301'), cliente, m.Fontes(finais={'sapl.antigo.ac.leg.br': NOVO})
    )
    assert (linha['status'], linha['fonte']) == ('ok', 'html')
    assert not any(u.startswith(ANTIGO) for u in sessao.pedidos)


def test_consultas_de_nomes_no_endereco_novo(cliente, sessao, tmp_path):
    fontes = m.Fontes(Cache(), {'sapl.riobranco.ac.leg.br': NOVO})
    _responder_consultas(sessao)  # roteiro em RB...
    sessao.responder(NOVO + 'api/materia/tipomaterialegislativa/1/', json_dados={'descricao': 'PL'})
    assert fontes.consultas(cliente, RB).tipo(1) == 'PL'
    assert sessao.pedidos == [NOVO + 'api/materia/tipomaterialegislativa/1/']


# --- Do começo ao fim --------------------------------------------------------


def test_projeto_com_casa_que_redireciona(projeto_tmp, cliente, sessao):
    falso = SaplFalso()
    falso.casa(
        NOVO,
        api=None,
        buscas={
            P: [f'<a href="{NOVO}materia/38415">a</a><a href="/materia/43301">b</a>'],
            '"orçamento"+"emenda+impositiva"': ['nada'],
        },
        html={
            '38415': 'sapl/sapl.cascavel.pr.leg.br/materia_38415.html',
            '43301': 'sapl/sapl.cascavel.pr.leg.br/materia_43301.html',
        },
    )
    sessao.rota(falso)
    # o endereço antigo só responde à página inicial, redirecionando
    sessao.responder(ANTIGO, texto='início', url_final=NOVO)
    pd.DataFrame({'UF': ['AC'], 'URL do serviço': [ANTIGO]}).to_excel(
        projeto_tmp / 'arquivos_csv' / 'casas_legislativas.xlsx', index=False
    )
    assert programa.main(roteiro('1', 'r', '2', '1', '2'), cliente, projeto_tmp) == 0
    assert [u for u in sessao.pedidos if u.startswith(ANTIGO)] == [ANTIGO]
    final = ler_final(projeto_tmp / 'r_proj' / 'r_resultado_final.csv')
    assert final['Link Casa'].tolist() == [ANTIGO, ANTIGO]
    assert final['Link Materia'].tolist() == [ANTIGO + 'materia/38415', ANTIGO + 'materia/43301']
    assert set(final['status']) == {'ok'}
    tabela = cl.ler_tabela_casas(projeto_tmp / 'r_proj' / 'casas_resultado.csv')
    assert tabela['url_final'].tolist() == [NOVO]
