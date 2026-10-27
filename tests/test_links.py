"""Extração dos links de matérias das páginas de busca reais."""
import csv

import pytest

from sapyl.links import links_da_pagina, raspar_resultados
from tests.apoio import ler_fixture

ESPERADOS = {
    'sapl.riobranco.ac.leg.br': ['46496', '34049', '37559', '44086'],
    'sapl.al.ac.leg.br': ['17764', '15951', '15821', '15817', '14270', '14296'],
    'sapl.cascavel.pr.leg.br': ['38415', '43301', '43300', '42263'],
}


@pytest.mark.parametrize('casa', sorted(ESPERADOS))
def test_links_das_paginas_reais(casa):
    links = links_da_pagina(ler_fixture(f'sapl/{casa}/busca_p1.html'), f'https://{casa}/')
    assert links == [f'https://{casa}/materia/{i}' for i in ESPERADOS[casa]]


@pytest.mark.parametrize('casa', sorted(ESPERADOS))
def test_busca_vazia_nao_tem_links(casa):
    assert links_da_pagina(ler_fixture(f'sapl/{casa}/busca_vazia.html'), f'https://{casa}/') == []


def test_exclui_paginacao_pdf_acessorio_e_outros_sites():
    html = '''
      <a href="/materia/10">ok</a>
      <a href="/materia/documentoacessorio/11">acessório</a>
      <a href="/materia/pesquisar-materia">pesquisa</a>
      <a href="/media/sapl/public/materialegislativa/2025/12/x.pdf">pdf</a>
      <a href="?page=2&q=x">página 2</a>
      <a href="https://outro.leg.br/materia/13">outro site</a>
      <a href="/materia/10/ta">texto articulado (mesma matéria)</a>
      <a href="https://sapl.a.leg.br/materia/14/">absoluto</a>
      <a href="/materia/15/autoria">aba de autoria</a>
    '''
    assert links_da_pagina(html, 'https://sapl.a.leg.br/') == [
        'https://sapl.a.leg.br/materia/10', 'https://sapl.a.leg.br/materia/14']


def test_raspar_resultados_le_o_arquivo_bruto(tmp_path):
    arquivo = tmp_path / 'cru.csv'
    with open(arquivo, 'w', newline='', encoding='utf-8') as f:
        escritor = csv.writer(f)
        escritor.writerow(['Indice', 'Casa', 'Palavra', 'Pagina', 'html', 'link'])
        escritor.writerow(['', 'https://sapl.cascavel.pr.leg.br/', '"plano+diretor"', 1,
                           ler_fixture('sapl/sapl.cascavel.pr.leg.br/busca_p1.html'), 'u'])
        escritor.writerow(['', 'https://sapl.cascavel.pr.leg.br/', '"lei+orgânica"', 1,
                           '<a href="/materia/38415">x</a>', 'u'])
    links = raspar_resultados(arquivo)
    assert len(links) == 5
    assert links[0] == {'Link Materia': 'https://sapl.cascavel.pr.leg.br/materia/38415',
                        'Link Casa': 'https://sapl.cascavel.pr.leg.br/',
                        'Palavras': '"plano+diretor"'}
    assert links[-1]['Palavras'] == '"lei+orgânica"'
