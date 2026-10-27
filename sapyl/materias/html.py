"""Extração dos dados de uma matéria pela página HTML (versões antigas do SAPL)."""
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sapyl.colunas import COLUNAS_DADOS, SEPARADOR
from sapyl.materias.valores import limpar

# Coluna -> sufixo do id da div na página HTML (`div_id_<sufixo>`)
CAMPOS_HTML = {
    'Ementa': 'ementa',
    'Ano': 'ano',
    'Data': 'data_apresentacao',
    'Numero': 'numero',
    'Observacao': 'observacao',
    'Tipo de Materia Legislativa': 'tipo',
    'Indexacao': 'indexacao',
    'Em Tramitacao': 'em_tramitacao',
    'Regime Tramitacao': 'regime_tramitacao',
    'Materia Anexada': 'materia_principal_set__materia_anexada',
    'Resultado': 'resultado',
    'Data Publicacao': 'data_publicacao',
    'Numero Protocolo': 'numero_protocolo',
}


def _valor_div(div):
    alvo = div.select_one('.form-control-static')
    if alvo is None:
        alvo = div
        for rotulo in div.select('.control-label'):
            rotulo.extract()
    itens = alvo.find_all('li')
    if itens:
        return SEPARADOR.join(limpar(li.get_text(' ')) for li in itens)
    return limpar(alvo.get_text(' '))


def _primeiro_valor(soup, sufixo):
    """Valor da primeira `div_id_<sufixo>` que não esteja vazia."""
    for div in soup.find_all('div', id=f'div_id_{sufixo}'):
        valor = _valor_div(div)
        if valor:
            return valor
    return ''


def extrair_html(html, casa_url):
    """Campos de COLUNAS_DADOS a partir da página HTML de uma matéria."""
    soup = BeautifulSoup(html, 'html.parser')
    titulo = soup.find('h1', class_='page-header')
    campos = {c: '' for c in COLUNAS_DADOS}
    campos['Titulo'] = limpar(titulo.get_text(' ')) if titulo else ''
    for coluna, sufixo in CAMPOS_HTML.items():
        campos[coluna] = _primeiro_valor(soup, sufixo)
    # Algumas casas repetem o bloco do texto original; só o primeiro tem o link
    for div in soup.find_all('div', id='div_id_texto_original'):
        a = div.find('a', href=True)
        if a:
            campos['texto_original'] = urljoin(casa_url, a['href'])
            break
    return campos
