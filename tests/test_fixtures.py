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
