"""Busca: paginação até 404, buscas incompletas, retomada."""

import pandas as pd
import pytest

from sapyl import busca as buscador
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import COLUNAS_PAGINAS
from sapyl.estado import Estado, ler_csv
from sapyl.links import raspar_paginas
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
    sessao.responder(
        buscador.url_busca(casa, palavra, n + 1),
        status=404,
        fixture=f'sapl/{casa[8:-1]}/busca_fim.html',
    )


def test_pagina_ate_404_e_grava_paginas(tmp_path, cliente, sessao, casas):
    _paginas(sessao, CV, P, 2, 'sapl/sapl.cascavel.pr.leg.br/busca_p1.html')
    _paginas(sessao, RB, P, 1, 'sapl/sapl.riobranco.ac.leg.br/busca_p1.html')
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'paginas.csv')

    assert estado.status('busca', buscador.chave_busca(CV, P)) == 'completa'
    assert estado.status('busca', buscador.chave_busca(RB, P)) == 'completa'
    assert not any('fora.do.ar' in u for u in sessao.pedidos)  # casa inativa
    paginas = ler_csv(tmp_path / 'paginas.csv', COLUNAS_PAGINAS)
    assert [(p['Casa'], p['Pagina']) for p in paginas] == [(CV, '1'), (CV, '2'), (RB, '1')]
    assert paginas[0]['links'].split()[0] == CV + 'materia/38415'
    assert len(raspar_paginas(tmp_path / 'paginas.csv')) == 4 + 4 + 4


def test_busca_vazia_e_completa(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    _paginas(sessao, CV, P, 1, 'sapl/sapl.cascavel.pr.leg.br/busca_vazia.html')
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'paginas.csv')
    assert estado.status('busca', buscador.chave_busca(CV, P)) == 'completa'
    assert raspar_paginas(tmp_path / 'paginas.csv') == []


def test_429_insistente_deixa_busca_incompleta_e_segue(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    sessao.responder(
        buscador.url_busca(CV, P, 1), fixture='sapl/sapl.cascavel.pr.leg.br/busca_p1.html'
    )
    sessao.responder(buscador.url_busca(CV, P, 2), status=429, headers={'Retry-After': '60'})
    _paginas(sessao, CV, Q, 1, 'sapl/sapl.cascavel.pr.leg.br/busca_p1.html')
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P, Q], cliente, estado, tmp_path / 'paginas.csv')
    assert estado.status('busca', buscador.chave_busca(CV, P)) == 'incompleta'
    assert estado.erro('busca', buscador.chave_busca(CV, P)) == 'página 2: HTTP 429'
    assert estado.status('busca', buscador.chave_busca(CV, Q)) == 'completa'


def test_500_na_primeira_pagina(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    sessao.responder(buscador.url_busca(CV, P, 1), status=500)
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'paginas.csv')
    assert estado.erro('busca', buscador.chave_busca(CV, P)) == 'página 1: HTTP 500'


def test_404_na_primeira_pagina_nao_e_busca_completa(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    sessao.responder(buscador.url_busca(CV, P, 1), status=404)
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'paginas.csv')
    assert estado.status('busca', buscador.chave_busca(CV, P)) == 'incompleta'
    assert '404 na primeira página' in estado.erro('busca', buscador.chave_busca(CV, P))


def test_retomada_pula_buscas_completas(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    estado = Estado(tmp_path / 'e.csv')
    estado.registrar('busca', buscador.chave_busca(CV, P), 'completa')
    estado.registrar('busca', buscador.chave_busca(CV, Q), 'incompleta', 'x')
    assert buscador.buscas_pendentes(casas, [P, Q], estado) == [(CV, Q)]
    _paginas(sessao, CV, Q, 1, 'sapl/sapl.cascavel.pr.leg.br/busca_p1.html')
    buscador.buscar(casas, [P, Q], cliente, estado, tmp_path / 'paginas.csv')
    assert all('plano' not in u for u in sessao.pedidos)
    assert estado.status('busca', buscador.chave_busca(CV, Q)) == 'completa'


def test_limite_de_paginas(tmp_path, cliente, sessao, monkeypatch):
    monkeypatch.setattr(buscador, 'MAX_PAGINAS', 3)
    casas = pd.DataFrame({'url': [CV], 'ativa': [True]})
    sessao.rota(lambda url: RespostaFalsa(200, 'x'))
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'paginas.csv')
    assert estado.erro('busca', buscador.chave_busca(CV, P)) == 'mais de 3 páginas'
    assert len(sessao.pedidos) == 3


# --- Arquivo de páginas só com os links (FR-21, NFR-3) ----------------------


def test_arquivo_de_paginas_nao_guarda_html(tmp_path, cliente, sessao):
    casas = pd.DataFrame({'url': [RB], 'ativa': [True]})
    _paginas(sessao, RB, P, 1, 'sapl/sapl.riobranco.ac.leg.br/busca_p1.html')
    estado = Estado(tmp_path / 'e.csv')
    buscador.buscar(casas, [P], cliente, estado, tmp_path / 'paginas.csv')
    texto = (tmp_path / 'paginas.csv').read_text(encoding='utf-8')
    assert '<' not in texto and 'html' not in texto.lower().replace('.html', '')
    [pagina] = ler_csv(tmp_path / 'paginas.csv', COLUNAS_PAGINAS)
    # na ordem da página
    assert pagina['links'].split() == [
        RB + 'materia/46496',
        RB + 'materia/34049',
        RB + 'materia/37559',
        RB + 'materia/44086',
    ]


def test_pagina_de_rio_branco_fica_10_vezes_menor(tmp_path, cliente, sessao):
    import csv

    from tests.apoio import ler_fixture

    casas = pd.DataFrame({'url': [RB], 'ativa': [True]})
    _paginas(sessao, RB, P, 1, 'sapl/sapl.riobranco.ac.leg.br/busca_p1.html')
    buscador.buscar(casas, [P], cliente, Estado(tmp_path / 'e.csv'), tmp_path / 'paginas.csv')
    # a mesma página no formato antigo (uma linha do arquivo bruto, com o HTML)
    with open(tmp_path / 'cru.csv', 'w', newline='', encoding='utf-8') as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(['Indice', 'Casa', 'Palavra', 'Pagina', 'html', 'link'])
        html = ler_fixture('sapl/sapl.riobranco.ac.leg.br/busca_p1.html')
        escritor.writerow(['', RB, P, 1, html, buscador.url_busca(RB, P, 1)])
    novo = (tmp_path / 'paginas.csv').stat().st_size
    antigo = (tmp_path / 'cru.csv').stat().st_size
    assert antigo >= 10 * novo, (antigo, novo)
