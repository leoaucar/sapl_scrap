"""Busca: paginação até 404, buscas incompletas, retomada."""
import pandas as pd
import pytest

import buscador
from estado import Estado, ler_csv
from http_sapl import ClienteSAPL
from raspador import raspar_resultados
from tests.apoio import RespostaFalsa

CV = 'https://sapl.cascavel.pr.leg.br/'
RB = 'https://sapl.riobranco.ac.leg.br/'
P = '"plano+diretor"'
Q = '"lei+orgânica"'


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


@pytest.fixture
def casas():
    return pd.DataFrame({'url': [CV, RB, 'https://fora.do.ar/'], 'ativa': [True, True, False]})


def _paginas(sessao, casa, palavra, n, fixture):
    for p in range(1, n + 1):
        sessao.responder(buscador.url_busca(casa, palavra, p), fixture=fixture)
    sessao.responder(buscador.url_busca(casa, palavra, n + 1), status=404,
                     fixture=f'sapl/{casa[8:-1]}/busca_fim.html')


def test_pagina_ate_404_e_grava_paginas(tmp_path, cliente, sessao, casas):
    _paginas(sessao, CV, P, 2, 'sapl/sapl.cascavel.pr.leg.br/busca_p1.html')
    _paginas(sessao, RB, P, 1, 'sapl/sapl.riobranco.ac.leg.br/busca_p1.html')
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'cru.csv')

    assert estado.status('busca', buscador.chave_busca(CV, P)) == 'completa'
    assert estado.status('busca', buscador.chave_busca(RB, P)) == 'completa'
    assert not any('fora.do.ar' in u for u in sessao.pedidos)   # casa inativa
    paginas = ler_csv(tmp_path / 'cru.csv', buscador.COLUNAS_CRU)
    assert [(p['Casa'], p['Pagina']) for p in paginas] == [(CV, '1'), (CV, '2'), (RB, '1')]
    assert len(raspar_resultados(tmp_path / 'cru.csv')) == 4 + 4 + 4


def test_busca_vazia_e_completa(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    _paginas(sessao, CV, P, 1, 'sapl/sapl.cascavel.pr.leg.br/busca_vazia.html')
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'cru.csv')
    assert estado.status('busca', buscador.chave_busca(CV, P)) == 'completa'
    assert raspar_resultados(tmp_path / 'cru.csv') == []


def test_429_insistente_deixa_busca_incompleta_e_segue(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    sessao.responder(buscador.url_busca(CV, P, 1), fixture='sapl/sapl.cascavel.pr.leg.br/busca_p1.html')
    sessao.responder(buscador.url_busca(CV, P, 2), status=429, headers={'Retry-After': '60'})
    _paginas(sessao, CV, Q, 1, 'sapl/sapl.cascavel.pr.leg.br/busca_p1.html')
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P, Q], cliente, estado, tmp_path / 'cru.csv')
    assert estado.status('busca', buscador.chave_busca(CV, P)) == 'incompleta'
    assert estado.erro('busca', buscador.chave_busca(CV, P)) == 'página 2: HTTP 429'
    assert estado.status('busca', buscador.chave_busca(CV, Q)) == 'completa'


def test_500_na_primeira_pagina(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    sessao.responder(buscador.url_busca(CV, P, 1), status=500)
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'cru.csv')
    assert estado.erro('busca', buscador.chave_busca(CV, P)) == 'página 1: HTTP 500'


def test_404_na_primeira_pagina_nao_e_busca_completa(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    sessao.responder(buscador.url_busca(CV, P, 1), status=404)
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'cru.csv')
    assert estado.status('busca', buscador.chave_busca(CV, P)) == 'incompleta'
    assert '404 na primeira página' in estado.erro('busca', buscador.chave_busca(CV, P))


def test_retomada_pula_buscas_completas(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    estado = Estado(tmp_path / 'e.csv')
    estado.registrar('busca', buscador.chave_busca(CV, P), 'completa')
    estado.registrar('busca', buscador.chave_busca(CV, Q), 'incompleta', 'x')
    assert buscador.buscas_pendentes(casas, [P, Q], estado) == [(CV, Q)]
    _paginas(sessao, CV, Q, 1, 'sapl/sapl.cascavel.pr.leg.br/busca_p1.html')
    buscador.buscar(casas, [P, Q], cliente, estado, tmp_path / 'cru.csv')
    assert all('plano' not in u for u in sessao.pedidos)
    assert estado.status('busca', buscador.chave_busca(CV, Q)) == 'completa'


def test_limite_de_paginas(tmp_path, cliente, sessao, monkeypatch):
    monkeypatch.setattr(buscador, 'MAX_PAGINAS', 3)
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    sessao.rota(lambda url: RespostaFalsa(200, 'x'))
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'cru.csv')
    assert estado.erro('busca', buscador.chave_busca(CV, P)) == 'mais de 3 páginas'
    assert len(sessao.pedidos) == 3
