"""As fixtures estão completas e não guardam dados pessoais de servidores."""

import json

from tests.apoio import PASTA_FIXTURES


def _indice():
    return json.loads((PASTA_FIXTURES / 'sapl' / 'index.json').read_text(encoding='utf-8'))


def test_todo_arquivo_do_indice_existe():
    for item in _indice():
        if item.get('method') == 'HEAD':
            continue
        assert (PASTA_FIXTURES / 'sapl' / item['name']).is_file(), item['name']


# Respostas da API de autoria e tramitação (T02), usadas nos testes de autoria
API_AUTORIA = {
    'sapl.riobranco.ac.leg.br': [
        'api_autoria_34049.json',
        'api_tramitacao_34049.json',
        'api_autor_145.json',
        'api_autoria_46496.json',
        'api_tramitacao_46496.json',
        'api_autor_41.json',
        'api_tipoautor_1.json',
        'api_tipoautor_8.json',
        'api_statustramitacao_59.json',
        'api_statustramitacao_2.json',
        'api_unidadetramitacao_60.json',
        'api_unidadetramitacao_16.json',
        'api_unidadetramitacao_29.json',
        'api_unidadetramitacao_17.json',
    ],
    'sapl.cascavel.pr.leg.br': [
        'api_autoria_38415.json',
        'api_tramitacao_38415.json',
        'api_autor_140.json',
        'api_autoria_43301.json',
        'api_tramitacao_43301.json',
        'api_autor_6.json',
        'api_tipoautor_1.json',
        'api_tipoautor_8.json',
        'api_statustramitacao_28.json',
        'api_statustramitacao_30.json',
        'api_unidadetramitacao_3.json',
        'api_unidadetramitacao_2.json',
    ],
}


def test_respostas_de_autoria_e_tramitacao_existem_e_estao_no_indice():
    nomes = {item['name'] for item in _indice()}
    for casa, arquivos in API_AUTORIA.items():
        for arquivo in arquivos:
            assert (PASTA_FIXTURES / 'sapl' / casa / arquivo).is_file(), arquivo
            assert f'{casa}/{arquivo}' in nomes, arquivo


def test_respostas_da_api_sem_ip_nem_usuario():
    def procurar(obj):
        if isinstance(obj, dict):
            for chave, valor in obj.items():
                if chave in ('ip', 'user', 'operadores'):
                    assert valor in (None, '', []), chave
                procurar(valor)
        elif isinstance(obj, list):
            for valor in obj:
                procurar(valor)

    arquivos = list((PASTA_FIXTURES / 'sapl').glob('*/api_*.json'))
    assert arquivos
    for arquivo in arquivos:
        procurar(json.loads(arquivo.read_text(encoding='utf-8')))


def test_fixtures_sinteticas_existem():
    for nome in ('materia_sem_data.html', 'materia_sem_pdf.html'):
        assert (PASTA_FIXTURES / 'sinteticas' / nome).is_file()
