"""Extração dos links de matérias das páginas de busca do SAPL.

As páginas de busca ficam no arquivo bruto do projeto
(`<projeto>_resultados_crus_casas.csv`, colunas
`Indice, Casa, Palavra, Pagina, html, link`).
"""
import csv
import sys

from bs4 import BeautifulSoup

from sapyl.materias import normalizar_link

# O HTML de cada página fica numa célula do CSV; aumenta o limite de tamanho
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def links_da_pagina(html, casa_url):
    """Links de matérias de uma página de busca, em ordem, sem repetição.

    Ficam de fora a paginação, PDFs (`/media/`), documentos acessórios e
    qualquer link que não seja `/materia/<id>`.
    """
    soup = BeautifulSoup(html, 'html.parser')
    vistos, links = set(), []
    for a in soup.find_all('a', href=True):
        normal = normalizar_link(casa_url, a['href'])
        if normal and normal[0] not in vistos:
            vistos.add(normal[0])
            links.append(normal[0])
    return links


def raspar_resultados(arquivo_cru):
    """Lê o arquivo bruto da busca e devolve dicts `Link Materia, Link Casa, Palavras`.

    Pode haver repetições (a mesma matéria em várias buscas); use
    `materias.deduplicar_links` em seguida.
    """
    links = []
    with open(arquivo_cru, newline='', encoding='utf-8') as arquivo:
        for linha in csv.DictReader(arquivo):
            if not linha.get('html') or not linha.get('Casa'):
                continue
            for link in links_da_pagina(linha['html'], linha['Casa']):
                links.append({'Link Materia': link, 'Link Casa': linha['Casa'],
                              'Palavras': linha['Palavra']})
    return links
