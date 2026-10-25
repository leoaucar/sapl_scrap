"""Matérias: chaves, duplicatas, extração (HTML e API) e escolha da fonte."""
import json
import logging

import pytest
import requests

import materias as m
from http_sapl import ClienteSAPL
from tests.apoio import ler_fixture

RB = 'https://sapl.riobranco.ac.leg.br/'
AL = 'https://sapl.al.ac.leg.br/'
CV = 'https://sapl.cascavel.pr.leg.br/'


@pytest.fixture
def cliente(sessao, relogio):
    return ClienteSAPL(sessao=sessao, relogio=relogio.agora, dormir=relogio.dormir)


# --- Chaves e normalização (FR-12) ------------------------------------------

@pytest.mark.parametrize('href', [
    '/materia/34049', '/materia/34049/', '/materia/34049/ta', 'materia/34049',
    'https://sapl.riobranco.ac.leg.br/materia/34049', 'http://sapl.riobranco.ac.leg.br/materia/34049/ta/',
    '/materia/34049?x=1#topo',
])
def test_normalizar_link(href):
    assert m.normalizar_link(RB, href) == (RB + 'materia/34049', '34049')


@pytest.mark.parametrize('href', [
    '/materia/documentoacessorio/1', '/materia/pesquisar-materia', '/materia/1/autoria',
    '/media/x.pdf', 'https://outro.leg.br/materia/1', '/sessao/1',
])
def test_normalizar_link_recusa_o_que_nao_e_materia(href):
    assert m.normalizar_link(RB, href) is None


def test_chave():
    assert m.chave(RB, '34049') == 'sapl.riobranco.ac.leg.br/34049'


# --- Duplicatas (FR-13) -----------------------------------------------------

def test_deduplicar_junta_palavras_na_ordem():
    links = [
        {'Link Materia': RB + 'materia/1', 'Link Casa': RB, 'Palavras': 'a'},
        {'Link Materia': RB + 'materia/2', 'Link Casa': RB, 'Palavras': 'a'},
        {'Link Materia': RB + 'materia/1/ta', 'Link Casa': RB, 'Palavras': 'b'},
        {'Link Materia': RB + 'materia/1', 'Link Casa': RB, 'Palavras': 'a'},
        {'Link Materia': CV + 'materia/1', 'Link Casa': CV, 'Palavras': 'c; a'},
        {'Link Materia': RB + 'pagina-qualquer', 'Link Casa': RB, 'Palavras': 'a'},
    ]
    unicos = m.deduplicar_links(links)
    assert [u['chave'] for u in unicos] == [
        'sapl.riobranco.ac.leg.br/1', 'sapl.riobranco.ac.leg.br/2', 'sapl.cascavel.pr.leg.br/1']
    assert unicos[0] == {'chave': 'sapl.riobranco.ac.leg.br/1', 'Link Materia': RB + 'materia/1',
                         'Link Casa': RB, 'Palavras': 'a; b', 'sapl_id': '1'}
    # mesmo id em casas diferentes não se junta
    assert unicos[2]['Palavras'] == 'c; a'


# --- Valores ----------------------------------------------------------------

def test_normalizacao_de_valores():
    assert m.limpar(' a \n\r b  ') == 'a b'
    assert m.limpar(None) == '' and m.limpar(2025) == '2025'
    assert m.data_br('2025-07-02') == '02/07/2025'
    assert m.data_br('02/07/2025') == '02/07/2025' and m.data_br(None) == ''
    assert m.data_hora_br('2026-09-21T13:25:49.124190-03:00') == '21/09/2026 13:25'
    assert m.data_hora_br('') == ''
    assert (m.sim_nao(True), m.sim_nao(False), m.sim_nao(None)) == ('Sim', 'Não', '')
    assert m.esquema_da_casa('http://sapl.a.leg.br/media/x.pdf', 'https://sapl.a.leg.br/') == \
        'https://sapl.a.leg.br/media/x.pdf'
    assert m.esquema_da_casa('http://outro/x.pdf', 'https://sapl.a.leg.br/') == 'http://outro/x.pdf'


# --- Extração HTML (FR-10, FR-10a, FR-11) -----------------------------------

ESPERADO_HTML = {
    ('sapl.al.ac.leg.br', '15951'): {
        'Titulo': 'Projeto de Lei nº 103 de 2024', 'Ano': '2024', 'Data': '09/07/2024',
        'Numero': '103', 'Tipo de Materia Legislativa': 'Projeto de Lei',
        'texto_original': AL + 'media/sapl/public/materialegislativa/2024/15951/pl-n-103-pedro_longo.pdf',
        'Em Tramitacao': 'Não', 'Regime Tramitacao': 'Ordinária', 'Observacao': ''},
    ('sapl.al.ac.leg.br', '17764'): {
        'Titulo': 'Moção nº 41 de 2025', 'Data': '23/09/2025', 'Tipo de Materia Legislativa': 'Moção',
        'Em Tramitacao': 'Sim'},
    ('sapl.cascavel.pr.leg.br', '38415'): {
        'Titulo': 'Requerimento nº 683 de 2025', 'Data': '08/12/2025', 'Numero': '683',
        'Observacao': 'Homenagem entregue pelo vereador Everton Guimarães em 10/12/2025.',
        'texto_original': CV + 'media/sapl/public/materialegislativa/2025/38415/req_683_2025.pdf'},
    ('sapl.cascavel.pr.leg.br', '43301'): {
        'Titulo': 'Projeto de Lei Ordinária nº 178 de 2026', 'Data': '20/10/2026',
        'Tipo de Materia Legislativa': 'Projeto de Lei Ordinária'},
    ('sapl.riobranco.ac.leg.br', '34049'): {
        'Titulo': 'Projeto de Lei Ordinária nº 89 de 2025', 'Data': '02/07/2025',
        'Numero Protocolo': '6078',
        # A página tem dois blocos de texto original; o link está no primeiro
        'texto_original': RB + 'media/sapl/public/materialegislativa/2025/34049/'
                               'projeto_de_lei_-_politica_municipal_de_habitacao_de_interesse_social_-_assinado.pdf'},
    ('sapl.riobranco.ac.leg.br', '46496'): {
        'Titulo': 'Veto nº 23 de 2026', 'Data': '16/09/2026', 'Tipo de Materia Legislativa': 'Veto',
        'Materia Anexada': 'Projeto de Lei Complementar nº 26 de 2025'},
}


@pytest.mark.parametrize('casa, sapl_id', sorted(ESPERADO_HTML))
def test_extrair_html_paginas_reais(casa, sapl_id):
    campos = m.extrair_html(ler_fixture(f'sapl/{casa}/materia_{sapl_id}.html'), f'https://{casa}/')
    assert list(campos) == m.COLUNAS_DADOS
    for coluna, valor in ESPERADO_HTML[(casa, sapl_id)].items():
        assert campos[coluna] == valor, coluna
    assert campos['Ementa'] and '\n' not in campos['Ementa']
    assert campos['Ultima Atualizacao'] == ''          # só existe na API
    assert not campos['Ementa'].startswith('Ementa')   # sem o rótulo


def test_ementa_completa_sem_quebras():
    campos = m.extrair_html(ler_fixture('sapl/sapl.riobranco.ac.leg.br/materia_34049.html'), RB)
    assert campos['Ementa'].startswith('PL: Minha casa, Minha Vida - Cidades Institui a Política')
    assert campos['Ementa'].endswith('Rio Branco – Acre.')


def test_extrair_html_sem_data_e_sem_pdf():
    sem_data = m.extrair_html(ler_fixture('sinteticas/materia_sem_data.html'), CV)
    assert sem_data['Data'] == '' and sem_data['Titulo']
    sem_pdf = m.extrair_html(ler_fixture('sinteticas/materia_sem_pdf.html'), AL)
    assert sem_pdf['texto_original'] == '' and sem_pdf['Titulo']


def test_extrair_html_de_pagina_desconhecida_da_campos_vazios():
    campos = m.extrair_html('<html><body><p>Erro</p></body></html>', RB)
    assert set(campos.values()) == {''}


def test_extrair_html_sem_form_control_static():
    html = ('<h1 class="page-header">X nº 1</h1><div id="div_id_ementa">'
            '<p class="control-label">Ementa</p>Texto antigo</div>')
    assert m.extrair_html(html, RB)['Ementa'] == 'Texto antigo'


# --- Extração API (FR-10, FR-10a, FR-10b) -----------------------------------

def _api(casa, sapl_id):
    return json.loads(ler_fixture(f'sapl/{casa}/api_materia_{sapl_id}.json'))


def _responder_consultas(sessao):
    sessao.responder(RB + 'api/materia/tipomaterialegislativa/1/',
                     fixture='sapl/sapl.riobranco.ac.leg.br/api_tipomateria_1.json')
    sessao.responder(RB + 'api/materia/tipomaterialegislativa/15/',
                     json_dados={'id': 15, '__str__': 'Veto', 'descricao': 'Veto'})
    sessao.responder(RB + 'api/materia/regimetramitacao/1/',
                     fixture='sapl/sapl.riobranco.ac.leg.br/api_regime_1.json')
    sessao.responder(RB + 'api/materia/materialegislativa/37559/',
                     json_dados={'id': 37559, '__str__': 'Projeto de Lei Complementar nº 26 de 2025'})


@pytest.mark.parametrize('sapl_id', ['34049', '46496'])
def test_api_e_html_dao_os_mesmos_campos(cliente, sessao, sapl_id):
    _responder_consultas(sessao)
    consultas = m.Consultas(cliente, RB)
    pela_api = m.extrair_api(_api('sapl.riobranco.ac.leg.br', sapl_id), RB, consultas)
    pelo_html = m.extrair_html(ler_fixture(f'sapl/sapl.riobranco.ac.leg.br/materia_{sapl_id}.html'), RB)
    assert list(pela_api) == m.COLUNAS_DADOS
    diferencas = {c for c in m.COLUNAS_DADOS if pela_api[c] != pelo_html[c]}
    assert diferencas == {'Ultima Atualizacao'}


def test_api_campos_proprios(cliente, sessao):
    _responder_consultas(sessao)
    campos = m.extrair_api(_api('sapl.riobranco.ac.leg.br', '46496'), RB, m.Consultas(cliente, RB))
    assert campos['Ultima Atualizacao'] == '15/10/2026 13:36'
    assert campos['texto_original'].startswith('https://sapl.riobranco.ac.leg.br/media/')
    assert campos['Materia Anexada'] == 'Projeto de Lei Complementar nº 26 de 2025'


def test_consultas_em_cache(cliente, sessao):
    _responder_consultas(sessao)
    consultas = m.Consultas(cliente, RB)
    for _ in range(3):
        assert consultas.tipo(1) == 'Projeto de Lei Ordinária'
        assert consultas.regime(1) == 'Ordinária'
    assert consultas.tipo(None) == ''
    assert sessao.contar('tipomaterialegislativa/1/') == 1
    assert sessao.contar('regimetramitacao/1/') == 1


def test_consulta_que_falha_deixa_campo_vazio(cliente, sessao, caplog):
    sessao.responder(CV + 'api/materia/tipomaterialegislativa/1/', status=404)
    sessao.responder(CV + 'api/materia/regimetramitacao/1/', texto='<html>não é json</html>')
    with caplog.at_level(logging.WARNING):
        campos = m.extrair_api(_api('sapl.cascavel.pr.leg.br', '43301'), CV, m.Consultas(cliente, CV))
    assert campos['Tipo de Materia Legislativa'] == '' and campos['Regime Tramitacao'] == ''
    assert campos['Titulo'] == 'Projeto de Lei Ordinária nº 178 de 2026'
    assert sum('Não foi possível obter o nome' in r.getMessage() for r in caplog.records) == 2


def test_api_nao_guarda_ip_nem_usuario(cliente, sessao):
    dados = _api('sapl.riobranco.ac.leg.br', '34049')
    dados.update(ip='10.0.0.1', user=99)
    _responder_consultas(sessao)
    campos = m.extrair_api(dados, RB, m.Consultas(cliente, RB))
    assert '10.0.0.1' not in json.dumps(campos) and 'ip' not in campos and 'user' not in campos


# --- Raspagem de uma matéria e escolha da fonte (FR-8, FR-9, FR-10) ---------

def _link(casa, sapl_id, palavras='"plano+diretor"'):
    return {'chave': m.chave(casa, sapl_id), 'Link Materia': f'{casa}materia/{sapl_id}',
            'Link Casa': casa, 'Palavras': palavras, 'sapl_id': sapl_id}


def test_raspar_pela_api(cliente, sessao):
    _responder_consultas(sessao)
    sessao.responder(m.url_api(RB, '34049'), fixture='sapl/sapl.riobranco.ac.leg.br/api_materia_34049.json')
    linha = m.raspar_materia(_link(RB, '34049'), cliente, m.Fontes())
    assert list(linha) == m.COLUNAS_MATERIAS
    assert (linha['status'], linha['erro'], linha['fonte']) == ('ok', '', 'api')
    assert linha['Titulo'] == 'Projeto de Lei Ordinária nº 89 de 2025'
    assert linha['chave'] == 'sapl.riobranco.ac.leg.br/34049' and linha['raspada_em']
    assert RB + 'materia/34049' not in sessao.pedidos     # só a API, sem a página HTML


def test_casa_sem_api_passa_para_html_e_continua_nele(cliente, sessao):
    fontes = m.Fontes()
    sessao.responder(m.url_api(AL, '15951'), status=404)
    sessao.responder(AL + 'materia/15951', fixture='sapl/sapl.al.ac.leg.br/materia_15951.html')
    sessao.responder(AL + 'materia/17764', fixture='sapl/sapl.al.ac.leg.br/materia_17764.html')
    primeira = m.raspar_materia(_link(AL, '15951'), cliente, fontes)
    segunda = m.raspar_materia(_link(AL, '17764'), cliente, fontes)
    assert (primeira['status'], primeira['fonte']) == ('ok', 'html')
    assert (segunda['status'], segunda['fonte']) == ('ok', 'html')
    assert fontes.de(AL) == 'html'
    assert sessao.contar('/api/') == 1              # a segunda já foi direto ao HTML


def test_api_que_nao_devolve_json_passa_para_html(cliente, sessao):
    fontes = m.Fontes()
    sessao.responder(m.url_api(CV, '43301'), texto='<html>login</html>')
    sessao.responder(CV + 'materia/43301', fixture='sapl/sapl.cascavel.pr.leg.br/materia_43301.html')
    linha = m.raspar_materia(_link(CV, '43301'), cliente, fontes)
    assert (linha['status'], linha['fonte']) == ('ok', 'html') and fontes.de(CV) == 'html'


def test_materia_apagada_nao_muda_a_fonte(cliente, sessao):
    fontes = m.Fontes()
    sessao.responder(m.url_api(RB, '1'), status=404)
    sessao.responder(RB + 'materia/1', status=404)
    linha = m.raspar_materia(_link(RB, '1'), cliente, fontes)
    assert (linha['status'], linha['erro']) == ('erro', 'HTTP 404')
    assert fontes.de(RB) == 'api'


def test_erro_depois_das_tentativas_vira_erro_sem_trocar_fonte(cliente, sessao):
    fontes = m.Fontes()
    sessao.responder(m.url_api(RB, '34049'), status=503)
    linha = m.raspar_materia(_link(RB, '34049'), cliente, fontes)
    assert (linha['status'], linha['erro'], linha['Titulo']) == ('erro', 'HTTP 503', '')
    assert fontes.de(RB) == 'api'
    assert sessao.pedidos == [m.url_api(RB, '34049')] * 4   # 4 tentativas na API, nenhuma no HTML


def test_429_insistente_nunca_vira_materia_vazia(cliente, sessao):
    fontes = m.Fontes()
    fontes.usar_html(RB, 'teste')
    sessao.responder(RB + 'materia/34049', status=429, headers={'Retry-After': '60'})
    linha = m.raspar_materia(_link(RB, '34049'), cliente, fontes)
    assert (linha['status'], linha['erro']) == ('erro', 'HTTP 429')


def test_pagina_200_sem_dados_e_erro(cliente, sessao):
    fontes = m.Fontes()
    fontes.usar_html(RB, 'teste')
    sessao.responder(RB + 'materia/5', texto='<html><body>Manutenção</body></html>')
    linha = m.raspar_materia(_link(RB, '5'), cliente, fontes)
    assert (linha['status'], linha['erro']) == ('erro', 'página sem dados de matéria')


def test_erro_de_rede_no_html(cliente, sessao):
    fontes = m.Fontes()
    fontes.usar_html(RB, 'teste')
    sessao.responder(RB + 'materia/5', erro=requests.ConnectionError())
    assert m.raspar_materia(_link(RB, '5'), cliente, fontes)['erro'] == 'conexao'


# --- Etapa de raspagem e retomada (FR-9, FR-18, FR-19) ----------------------

from estado import Estado, ler_csv  # noqa: E402


def _links_cascavel():
    return [_link(CV, '38415'), _link(CV, '43301'), _link(CV, '99')]


def _responder_cascavel(sessao, falha_99=True):
    for i in ('38415', '43301'):
        sessao.responder(m.url_api(CV, i), status=404)
        sessao.responder(CV + f'materia/{i}', fixture=f'sapl/sapl.cascavel.pr.leg.br/materia_{i}.html')
    sessao.responder(CV + 'materia/99', status=503 if falha_99 else 200,
                     fixture='sapl/sapl.cascavel.pr.leg.br/materia_38415.html')


def test_raspar_todas_grava_cada_materia_e_o_estado(tmp_path, cliente, sessao):
    _responder_cascavel(sessao)
    estado = Estado(tmp_path / 'e.csv')
    m.raspar_todas(_links_cascavel(), cliente, estado, tmp_path / 'mat.csv')
    linhas = ler_csv(tmp_path / 'mat.csv', m.COLUNAS_MATERIAS)
    assert [(l['chave'], l['status']) for l in linhas] == [
        ('sapl.cascavel.pr.leg.br/38415', 'ok'), ('sapl.cascavel.pr.leg.br/43301', 'ok'),
        ('sapl.cascavel.pr.leg.br/99', 'erro')]
    assert estado.contagens('materia') == {'ok': 2, 'erro': 1}


def test_retomada_pula_ok_e_refaz_erro(tmp_path, cliente, sessao):
    _responder_cascavel(sessao)
    estado = Estado(tmp_path / 'e.csv')
    m.raspar_todas(_links_cascavel(), cliente, estado, tmp_path / 'mat.csv')
    estado.fechar()

    sessao.pedidos.clear()
    sessao.responder(m.url_api(CV, '99'), status=404)
    sessao.limpar(CV + 'materia/99').responder(
        CV + 'materia/99', fixture='sapl/sapl.cascavel.pr.leg.br/materia_38415.html')
    estado = Estado(tmp_path / 'e.csv')
    m.raspar_todas(_links_cascavel(), cliente, estado, tmp_path / 'mat.csv')
    # só a matéria com erro é pedida de novo (nova execução testa a API outra vez)
    assert sessao.pedidos == [m.url_api(CV, '99'), CV + 'materia/99']
    assert estado.status('materia', 'sapl.cascavel.pr.leg.br/99') == 'ok'


def test_materia_gravada_sem_estado_e_refeita(tmp_path, cliente, sessao):
    _responder_cascavel(sessao, falha_99=False)
    links = _links_cascavel()
    # simula queda depois de gravar a matéria e antes de gravar o estado
    from estado import ArquivoCSV
    arquivo = ArquivoCSV(tmp_path / 'mat.csv', m.COLUNAS_MATERIAS)
    arquivo.anexar({**m.linha_vazia(links[0]), 'status': 'ok', 'Titulo': 'antigo'})
    arquivo.fechar()
    estado = Estado(tmp_path / 'e.csv')
    m.raspar_todas(links, cliente, estado, tmp_path / 'mat.csv')
    assert sessao.contar('materia/38415') >= 1
    assert estado.status('materia', links[0]['chave']) == 'ok'


def test_salvar_e_ler_links(tmp_path):
    links = m.deduplicar_links([{'Link Materia': RB + 'materia/1', 'Link Casa': RB, 'Palavras': 'a'}])
    m.salvar_links(links, tmp_path / 'links.csv')
    assert m.ler_links(tmp_path / 'links.csv') == links
