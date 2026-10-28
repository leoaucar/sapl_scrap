"""Links de matérias: chave, forma canônica, duplicatas e arquivos de links.

Cada matéria é identificada pela chave `<host>/<sapl_id>` (ex.:
`sapl.riobranco.ac.leg.br/34049`), nunca pela posição na tabela.

Os links vêm das páginas de busca. Cada página fica em
`<projeto>_paginas_busca.csv` só com os links de matérias encontrados
(COLUNAS_PAGINAS). Projetos das versões até 0.1 têm, em vez disso (ou além
disso, se foram retomados), o arquivo bruto `<projeto>_resultados_crus_casas.csv`,
com o HTML de cada página; ele continua sendo lido.
"""

import csv
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from sapyl.colunas import COLUNAS_LINKS, COLUNAS_PAGINAS, SEPARADOR, Linha
from sapyl.estado import ler_csv

# O HTML de cada página fica numa célula do CSV; aumenta o limite de tamanho
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

_RE_MATERIA = re.compile(r'^/materia/(\d+)(?:/ta)?/?$')


def host(url: str) -> str:
    """Host de uma URL (`sapl.x.leg.br`), ou ''."""
    return urlparse(url).hostname or ''


def chave(casa_url: str, sapl_id: str) -> str:
    """Chave da matéria: `<host>/<sapl_id>`."""
    return f'{host(casa_url)}/{sapl_id}'


def normalizar_link(casa_url: str, href: object) -> tuple[str, str] | None:
    """Link canônico de uma matéria e seu id, ou None se não for página de matéria.

    Aceita links relativos e absolutos; remove `/ta` (texto articulado), barra
    final, parâmetros e âncoras; usa o esquema (https) da casa.
    """
    absoluto = urljoin(casa_url, str(href).strip())
    partes, casa = urlparse(absoluto), urlparse(casa_url)
    if partes.hostname != casa.hostname:
        return None
    encontrado = _RE_MATERIA.match(partes.path)
    if not encontrado:
        return None
    sapl_id = encontrado.group(1)
    return f'{casa.scheme}://{casa.netloc}/materia/{sapl_id}', sapl_id


def deduplicar_links(links: Iterable[Linha]) -> list[Linha]:
    """Junta links repetidos (mesma chave) numa linha só.

    `links`: lista de dicts com `Link Materia`, `Link Casa`, `Palavras` (uma
    ou mais palavras separadas por '; '). Devolve lista de dicts com
    COLUNAS_LINKS, na ordem da primeira aparição; `Palavras` lista todas as
    palavras que encontraram a matéria.
    """
    unicos = {}
    for item in links:
        normal = normalizar_link(item['Link Casa'], item['Link Materia'])
        if normal is None:
            continue
        link, sapl_id = normal
        k = chave(item['Link Casa'], sapl_id)
        palavras = [p for p in str(item.get('Palavras', '')).split(SEPARADOR) if p]
        if k not in unicos:
            unicos[k] = {
                'chave': k,
                'Link Materia': link,
                'Link Casa': item['Link Casa'],
                'Palavras': [],
                'sapl_id': sapl_id,
            }
        for p in palavras:
            if p not in unicos[k]['Palavras']:
                unicos[k]['Palavras'].append(p)
    for item in unicos.values():
        item['Palavras'] = SEPARADOR.join(item['Palavras'])
    return list(unicos.values())


def links_da_pagina(html: str, casa_url: str) -> list[str]:
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


def raspar_resultados(arquivo_cru: str | Path) -> list[Linha]:
    """Lê o arquivo bruto da busca e devolve dicts `Link Materia, Link Casa, Palavras`.

    Pode haver repetições (a mesma matéria em várias buscas); use
    `deduplicar_links` em seguida.
    """
    links = []
    with open(arquivo_cru, newline='', encoding='utf-8') as arquivo:
        for linha in csv.DictReader(arquivo):
            if not linha.get('html') or not linha.get('Casa'):
                continue
            for link in links_da_pagina(linha['html'], linha['Casa']):
                links.append(
                    {'Link Materia': link, 'Link Casa': linha['Casa'], 'Palavras': linha['Palavra']}
                )
    return links


def raspar_paginas(arquivo_paginas: str | Path) -> list[Linha]:
    """Lê o arquivo de páginas da busca e devolve dicts `Link Materia, Link Casa, Palavras`.

    Pode haver repetições; use `deduplicar_links` em seguida.
    """
    links = []
    for linha in ler_csv(arquivo_paginas, COLUNAS_PAGINAS):
        for link in linha['links'].split():
            links.append(
                {'Link Materia': link, 'Link Casa': linha['Casa'], 'Palavras': linha['Palavra']}
            )
    return links


def links_das_buscas(
    arquivo_paginas: str | Path, arquivo_cru: str | Path | None = None
) -> list[Linha]:
    """Links de todas as buscas do projeto: o arquivo bruto antigo (se houver) e o novo.

    Nessa ordem: as matérias achadas antes da atualização do programa vêm
    primeiro, como vinham. Pode haver repetições.
    """
    links = []
    if arquivo_cru is not None and Path(arquivo_cru).exists():
        links += raspar_resultados(arquivo_cru)
    if Path(arquivo_paginas).exists():
        links += raspar_paginas(arquivo_paginas)
    return links


def salvar_links(links: list[Linha], caminho: str | Path) -> None:
    """Grava a lista de links únicos (COLUNAS_LINKS), substituindo o arquivo."""
    with open(caminho, 'w', newline='', encoding='utf-8') as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_LINKS, extrasaction='ignore')
        escritor.writeheader()
        escritor.writerows(links)


def ler_links(caminho: str | Path) -> list[Linha]:
    """Lê a lista de links únicos gravada por `salvar_links`."""
    return ler_csv(caminho, COLUNAS_LINKS)
