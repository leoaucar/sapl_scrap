"""Autoria e tramitação: API, HTML e o arquivo de saída."""

import json
import re

import pandas as pd
import pytest

from sapyl import autoria as at
from sapyl import materias as m
from sapyl.cliente_http import ClienteSAPL
from sapyl.estado import Cache
from tests.apoio import PASTA_FIXTURES

AL = 'https://sapl.al.ac.leg.br/'
RB = 'https://sapl.riobranco.ac.leg.br/'


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


def test_autoria_e_tramitacao_das_paginas_reais(cliente, sessao):
    sessao.responder(
        AL + 'materia/15951/autoria', fixture='sapl/sapl.al.ac.leg.br/materia_15951_autoria.html'
    )
    sessao.responder(
        AL + 'materia/15951/tramitacao',
        fixture='sapl/sapl.al.ac.leg.br/materia_15951_tramitacao.html',
    )
    assert at.autoria_html(AL + 'materia/15951/ta', cliente) == ('PEDRO LONGO (Parlamentar)', '')
    tramite, erro = at.tramitacao_html(AL + 'materia/15951/', cliente)
    assert erro == ''
    assert tramite == (
        '10/07/2024 | SUB SEC ATIV LEGISLATIVA - SALEGIS | SECRETARIA EXECUTIVA - SE | '
        'Autógrafo enviado'
    )


def test_falha_e_registrada(cliente, sessao):
    sessao.responder(RB + 'materia/1/autoria', status=503)
    sessao.responder(RB + 'materia/1/tramitacao', status=404)
    assert at.autoria_html(RB + 'materia/1', cliente) == ('', 'HTTP 503')
    assert at.tramitacao_html(RB + 'materia/1', cliente) == ('', 'HTTP 404')


def test_pagina_sem_tabela(cliente, sessao):
    sessao.responder(RB + 'materia/2/tramitacao', texto='<p>Nenhuma tramitação</p>')
    assert at.tramitacao_html(RB + 'materia/2', cliente) == ('', '')


# --- Pela API (FR-14, FR-15, FR-16) -----------------------------------------


CV = 'https://sapl.cascavel.pr.leg.br/'
RECURSOS = {
    'autor': 'base/autor',
    'tipoautor': 'base/tipoautor',
    'statustramitacao': 'materia/statustramitacao',
    'unidadetramitacao': 'materia/unidadetramitacao',
}
# Texto esperado (o mesmo das abas HTML salvas em 24/10/2026)
ESPERADO = {
    (RB, '34049'): (
        'Zé Lopes (Parlamentar)',
        '21/09/2026 | Redação Legislativa - RL | Diretoria Legislativa - DILEGIS | '
        'Matéria Encaminhada ao Executivo Municipal',
    ),
    (RB, '46496'): (
        'Executivo Municipal - sapladm (Poder Executivo)',
        '15/10/2026 | Chefe de gabinete da Presidência - CGP | Comissões Técnicas - CTEC | '
        'Aguardando emissão de parecer da comissão',
    ),
    (CV, '38415'): (
        'Everton Guimarães (Parlamentar)',
        '09/12/2025 | Plenário da Câmara - PLEN | '
        'Depto. Apoio às Sessões e ao Proc. Legislativo - DASPL | '
        'Proposição lida e apresentada em Plenário',
    ),
    (CV, '43301'): (
        'Prefeito Municipal - Prefeito (Poder Executivo)',
        '20/10/2026 | Plenário da Câmara - PLEN | '
        'Depto. Apoio às Sessões e ao Proc. Legislativo - DASPL | '
        'Aguardando a inclusão na ordem do dia',
    ),
}


def _pasta(casa):
    return f'sapl/{casa[8:-1]}/'


def _responder_api(sessao, casa):
    """Roteiro da API da casa a partir das fixtures salvas na T02."""
    pasta = PASTA_FIXTURES / _pasta(casa)
    for arquivo in pasta.glob('api_*.json'):
        achado = re.match(r'api_(autoria|tramitacao)_(\d+)\.json$', arquivo.name)
        if achado:
            lista, i = achado.groups()
            sessao.responder(
                f'{casa}api/materia/{lista}/?materia={i}', fixture=_pasta(casa) + arquivo.name
            )
            continue
        achado = re.match(r'api_(\w+?)_(\d+)\.json$', arquivo.name)
        if achado and achado.group(1) in RECURSOS:
            recurso, i = achado.groups()
            sessao.responder(
                f'{casa}api/{RECURSOS[recurso]}/{i}/', fixture=_pasta(casa) + arquivo.name
            )


def _responder_html(sessao, casa, i):
    for aba in ('autoria', 'tramitacao'):
        sessao.responder(
            f'{casa}materia/{i}/{aba}', fixture=f'{_pasta(casa)}materia_{i}_{aba}.html'
        )


@pytest.mark.parametrize('casa, sapl_id', list(ESPERADO), ids=lambda v: str(v))
def test_api_e_html_dao_o_mesmo_texto(cliente, sessao, casa, sapl_id):
    _responder_api(sessao, casa)
    _responder_html(sessao, casa, sapl_id)
    pela_api = at.raspar_autoria(f'{casa}materia/{sapl_id}', cliente, m.Fontes())
    cache_html = Cache()
    cache_html.guardar_fonte(casa[8:-1], 'html')
    pelo_html = at.raspar_autoria(f'{casa}materia/{sapl_id}', cliente, m.Fontes(cache_html))
    assert pela_api['fonte_autoria'] == 'api' and pelo_html['fonte_autoria'] == 'html'
    assert (pela_api['Autoria'], pela_api['Tramite']) == ESPERADO[(casa, sapl_id)]
    assert (pelo_html['Autoria'], pelo_html['Tramite']) == ESPERADO[(casa, sapl_id)]
    assert pela_api['status_autoria'] == pela_api['status_tramitacao'] == 'ok'


def test_nomes_consultados_uma_vez(cliente, sessao):
    _responder_api(sessao, RB)
    fontes = m.Fontes()
    sessao.responder(
        f'{RB}api/materia/autoria/?materia=99',
        fixture=_pasta(RB) + 'api_autoria_34049.json',  # o mesmo autor (145)
    )
    sessao.responder(f'{RB}api/materia/tramitacao/?materia=99', json_dados={'results': []})
    at.raspar_autoria(RB + 'materia/34049', cliente, fontes)
    segunda = at.raspar_autoria(RB + 'materia/99', cliente, fontes)
    assert segunda['Autoria'] == 'Zé Lopes (Parlamentar)'
    assert segunda['Tramite'] == '' and segunda['status_tramitacao'] == 'ok'  # sem trâmite
    assert sessao.contar('/api/base/autor/145/') == 1
    assert sessao.contar('/api/base/tipoautor/1/') == 1


@pytest.mark.parametrize(
    'resposta', [{'status': 404}, {'texto': '<html>login</html>'}], ids=['404', 'nao-json']
)
def test_casa_sem_api_passa_para_o_html(cliente, sessao, resposta):
    for i in ('15951', '17764'):
        sessao.responder(f'{AL}api/materia/autoria/?materia={i}', **resposta)
        sessao.responder(f'{AL}api/materia/tramitacao/?materia={i}', **resposta)
        _responder_html(sessao, AL, i)
    fontes = m.Fontes()
    primeira = at.raspar_autoria(AL + 'materia/15951', cliente, fontes)
    segunda = at.raspar_autoria(AL + 'materia/17764', cliente, fontes)
    assert primeira['Autoria'] == 'PEDRO LONGO (Parlamentar)'
    assert primeira['fonte_autoria'] == segunda['fonte_autoria'] == 'html'
    assert fontes.de(AL) == 'html'
    assert sessao.contar('/api/') == 1  # só a primeira sondagem


def test_falha_da_api_e_registrada_sem_trocar_a_casa(cliente, sessao):
    sessao.responder(f'{RB}api/materia/autoria/?materia=7', status=503)
    sessao.responder(f'{RB}api/materia/tramitacao/?materia=7', json_dados={'results': []})
    fontes = m.Fontes()
    linha = at.raspar_autoria(RB + 'materia/7', cliente, fontes)
    assert (linha['status_autoria'], linha['status_tramitacao']) == ('erro', 'ok')
    assert linha['erro_autoria_tramitacao'] == 'autoria: HTTP 503'
    assert fontes.de(RB) == 'api'
    assert not any('/materia/7/autoria' in u for u in sessao.pedidos)


def test_lista_de_autores_em_varias_paginas(cliente, sessao):
    pagina1 = {
        'pagination': {
            'links': {
                'next': 'http://sapl.riobranco.ac.leg.br/api/materia/autoria/?materia=8&page=2'
            }
        },
        'results': [{'autor': 145}],
    }
    pagina2 = {'pagination': {'links': {'next': None}}, 'results': [{'autor': 41}]}
    _responder_api(sessao, RB)
    sessao.responder(f'{RB}api/materia/autoria/?materia=8', json_dados=pagina1)
    sessao.responder(f'{RB}api/materia/autoria/?materia=8&page=2', json_dados=pagina2)
    sessao.responder(f'{RB}api/materia/tramitacao/?materia=8', json_dados={'results': []})
    linha = at.raspar_autoria(RB + 'materia/8', cliente, m.Fontes())
    assert (
        linha['Autoria']
        == 'Zé Lopes (Parlamentar); Executivo Municipal - sapladm (Poder Executivo)'
    )
    assert json.dumps(linha)  # só texto


# --- Planilha inteira, com retomada (FR-17, FR-18) --------------------------


def _entrada(tmp_path, links, indice=False):
    caminho = tmp_path / 'resultado.csv'
    pd.DataFrame({'Link Materia': links, 'Titulo': [f't{i}' for i in range(len(links))]}).to_csv(
        caminho, index=indice
    )
    return caminho


def _sem_api(sessao, casa, *ids):
    for i in ids:
        for lista in ('autoria', 'tramitacao'):
            sessao.responder(f'{casa}api/materia/{lista}/?materia={i}', status=404)


def test_processar_grava_copia_com_as_colunas_novas(tmp_path, cliente, sessao):
    entrada = _entrada(tmp_path, [AL + 'materia/15951', AL + 'materia/15951/ta', 'lixo'], True)
    original = entrada.read_bytes()
    _sem_api(sessao, AL, '15951')
    _responder_html(sessao, AL, '15951')
    saida, contagens = at.processar(entrada, cliente)
    assert entrada.read_bytes() == original
    assert saida == tmp_path / 'resultado_autoria_tramitacao.csv'
    tabela = pd.read_csv(saida, dtype=str, keep_default_na=False)
    assert list(tabela.columns) == ['Link Materia', 'Titulo', *at.COLUNAS_AUTORIA]
    assert tabela['Autoria'].tolist()[:2] == ['PEDRO LONGO (Parlamentar)'] * 2  # mesma matéria
    assert tabela['erro_autoria_tramitacao'][2] == 'link de matéria inválido'
    assert contagens == {'ok': 1}
    assert sessao.contar('/materia/15951/autoria') == 1  # repetida: buscada uma vez


def test_interrompida_e_retomada_so_busca_o_que_falta(tmp_path, cliente, sessao, monkeypatch):
    ids = ['15951', '17764']
    entrada = _entrada(tmp_path, [AL + f'materia/{i}' for i in ids] + [RB + 'materia/5'])
    _sem_api(sessao, AL, *ids)
    for i in ids:
        _responder_html(sessao, AL, i)
    sessao.responder(f'{RB}api/materia/autoria/?materia=5', status=503)
    sessao.responder(f'{RB}api/materia/tramitacao/?materia=5', json_dados={'results': []})

    original, vezes = at.raspar_autoria, []

    def cair_na_segunda(link, *args):
        vezes.append(link)
        if len(vezes) == 2:
            raise KeyboardInterrupt
        return original(link, *args)

    monkeypatch.setattr(at, 'raspar_autoria', cair_na_segunda)
    with pytest.raises(KeyboardInterrupt):
        at.processar(entrada, cliente)
    monkeypatch.setattr(at, 'raspar_autoria', original)
    assert not (tmp_path / 'resultado_autoria_tramitacao.csv').exists()

    sessao.pedidos.clear()
    saida, contagens = at.processar(entrada, cliente)
    assert not any('15951' in u for u in sessao.pedidos)  # já feita antes da queda
    assert contagens == {'ok': 2, 'erro': 1}
    tabela = pd.read_csv(saida, dtype=str, keep_default_na=False)
    assert tabela['status_autoria'].tolist() == ['ok', 'ok', 'erro']

    # a que falhou é tentada de novo numa próxima execução; as ok, não
    sessao.limpar(f'{RB}api/materia/autoria/?materia=5')
    sessao.responder(f'{RB}api/materia/autoria/?materia=5', json_dados={'results': []})
    sessao.pedidos.clear()
    _, contagens = at.processar(entrada, cliente)
    assert contagens == {'ok': 3}
    assert all('materia=5' in u for u in sessao.pedidos)


def test_planilha_sem_link_materia(tmp_path, cliente):
    caminho = tmp_path / 'x.csv'
    caminho.write_text('Titulo\na\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Link Materia'):
        at.processar(caminho, cliente)
