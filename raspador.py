"""Raspagem das páginas do SAPL.

Duas etapas:
1. `raspar_resultados`: lê o HTML bruto das páginas de busca e extrai os
   links que apontam para matérias legislativas.
2. `raspar_materia_legislativa` / `atualizar_materia_legislativa`: abre cada
   matéria e extrai seus campos (título, ementa, ano, etc.).
"""
from bs4 import BeautifulSoup
import pandas as pd
import requests


# Trechos de URL que indicam links que NÃO são páginas de matéria
# (paginação da busca, arquivos de mídia e documentos acessórios).
# TODO: considerar também sessões e normas jurídicas.
FILTROS_LINKS_EXCLUIDOS = ('pesquisar', 'media', 'documentoacessorio')


def raspar_resultados(resultados_busca):
    """Extrai os links de matérias do HTML bruto das páginas de busca.

    `resultados_busca` é o CSV `<projeto>_resultados_crus_casas.csv`.
    Retorna uma lista de [link_materia, link_casa, palavra].
    """
    links_totais = []
    resultados = pd.read_csv(resultados_busca, encoding='UTF-8')
    for i in range(len(resultados)):
        html = resultados.loc[i, 'html']
        link = resultados.loc[i, 'Casa']
        palavra = resultados.loc[i, 'Palavra']
        soup = BeautifulSoup(html)
        for a in soup.find_all('a', href=True):
            # Remove a barra final da URL da casa e concatena o href relativo
            links_totais.append([str(link)[:-1] + a['href'], link, palavra])

    links_materias = []
    for link in links_totais:
        if 'materia' in link[0] and not any(f in link[0] for f in FILTROS_LINKS_EXCLUIDOS):
            links_materias.append(link)
    # TODO: remover links duplicados (a mesma matéria aparece em várias buscas)
    return links_materias


def _ultimo_texto(soup, tag, atributos):
    """Texto (sem espaços nas pontas) do último elemento encontrado, ou ''."""
    texto = ''
    for elemento in soup.find_all(tag, atributos):
        texto = elemento.text
    return texto.strip()


def _ultimo_link(soup, id_div):
    """href do primeiro <a> dentro da última div com esse id, ou ''."""
    link = ''
    for div in soup.find_all('div', {"id": id_div}):
        try:
            link = str(div.find('a')['href'])
        except:
            link = ''
    return link


def _extrair_campos_materia(soup):
    """Extrai os campos de uma página de matéria, na ordem das colunas finais."""
    return [
        _ultimo_texto(soup, 'h1', {"class": "page-header"}),   # titulo
        _ultimo_texto(soup, 'div', {"id": "div_id_ementa"}),
        _ultimo_texto(soup, 'div', {"id": "div_id_ano"}),
        _ultimo_texto(soup, 'div', {"id": "div_id_data"}),
        _ultimo_texto(soup, 'div', {"id": "div_id_numero"}),
        _ultimo_texto(soup, 'div', {"id": "div_id_observacao"}),
        _ultimo_texto(soup, 'div', {"id": "div_id_assuntos"}),
        _ultimo_texto(soup, 'div', {"id": "div_id_tipo"}),      # tipo de matéria
        _ultimo_link(soup, 'div_id_texto_original'),
        _ultimo_link(soup, 'div_id_texto_integral'),
    ]


def _raspar_links(links_achados):
    """Baixa cada matéria (2ª coluna da tabela) e acrescenta seus campos à linha."""
    resultados = []
    indice = 0
    for i in links_achados.iloc[:, 1]:
        i = i.replace('/ta', '')  # usa a página da matéria, não a do texto articulado
        response = requests.get(i)
        dados_atuais = list(links_achados.iloc[indice, :])
        soup = BeautifulSoup(response.text)
        dados_atuais.extend(_extrair_campos_materia(soup))
        resultados.append(dados_atuais)
        print(dados_atuais)
        indice = indice + 1
    return resultados


def raspar_materia_legislativa(conteudo):
    """Raspa as matérias listadas em `<projeto>_links_totais.csv` (projeto novo)."""
    links_achados = pd.read_csv(conteudo)
    return _raspar_links(links_achados)


def atualizar_materia_legislativa(conteudo):
    """Raspa de novo as matérias de um `<projeto>_resultado_final.csv` existente."""
    links_achados = pd.read_csv(conteudo, index_col=0)
    # links_achados = links_achados[links_achados['Relevante']=='Sim']
    return _raspar_links(links_achados)
