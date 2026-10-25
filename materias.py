"""Matérias legislativas: identificação, duplicatas e extração dos dados.

Cada matéria é identificada pela chave `<host>/<sapl_id>` (ex.:
`sapl.riobranco.ac.leg.br/34049`), nunca pela posição na tabela.

Os dados vêm da API JSON do SAPL (`/api/materia/materialegislativa/<id>/`)
quando a casa tem a API, ou da página HTML da matéria (versões antigas do
SAPL). As duas fontes produzem as mesmas colunas (`COLUNAS_FINAIS`).
"""
import csv
from datetime import datetime
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from estado import ArquivoCSV, ler_csv
import registro

# Colunas do resultado final, na ordem. As 11 primeiras são as da versão
# anterior (sem `Assuntos` e `texto_integral`, que não existem mais no SAPL).
COLUNAS_DADOS = [
    'Titulo', 'Ementa', 'Ano', 'Data', 'Numero', 'Observacao',
    'Tipo de Materia Legislativa', 'texto_original',
    'Indexacao', 'Em Tramitacao', 'Regime Tramitacao', 'Materia Anexada', 'Resultado',
    'Data Publicacao', 'Numero Protocolo', 'Ultima Atualizacao',
]
COLUNAS_FINAIS = (['Link Materia', 'Link Casa', 'Palavras'] + COLUNAS_DADOS
                  + ['sapl_id', 'fonte', 'status', 'erro', 'raspada_em',
                     'arquivo_pdf', 'download_status'])
# O arquivo de matérias raspadas guarda também a chave
COLUNAS_MATERIAS = ['chave'] + COLUNAS_FINAIS
COLUNAS_LINKS = ['chave', 'Link Materia', 'Link Casa', 'Palavras', 'sapl_id']

SEPARADOR = '; '
_RE_MATERIA = re.compile(r'^/materia/(\d+)(?:/ta)?/?$')

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

log = registro.logger('materias')


# --- Chaves e links ---------------------------------------------------------

def host(url):
    return urlparse(url).hostname or ''


def chave(casa_url, sapl_id):
    return f'{host(casa_url)}/{sapl_id}'


def normalizar_link(casa_url, href):
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


def deduplicar_links(links):
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
            unicos[k] = {'chave': k, 'Link Materia': link, 'Link Casa': item['Link Casa'],
                         'Palavras': [], 'sapl_id': sapl_id}
        for p in palavras:
            if p not in unicos[k]['Palavras']:
                unicos[k]['Palavras'].append(p)
    for item in unicos.values():
        item['Palavras'] = SEPARADOR.join(item['Palavras'])
    return list(unicos.values())


# --- Normalização de valores ------------------------------------------------

def limpar(valor):
    """Texto numa linha só, sem espaços sobrando; None vira ''."""
    if valor is None:
        return ''
    return ' '.join(str(valor).split())


def data_br(valor):
    """'2025-07-02' -> '02/07/2025'. Outros formatos voltam como vieram."""
    valor = limpar(valor)
    try:
        return datetime.strptime(valor[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return valor


def data_hora_br(valor):
    """'2026-09-21T13:25:49.124190-03:00' -> '21/09/2026 13:25' (hora local do site)."""
    valor = limpar(valor)
    try:
        return datetime.strptime(valor[:16], '%Y-%m-%dT%H:%M').strftime('%d/%m/%Y %H:%M')
    except ValueError:
        return valor


def sim_nao(valor):
    if valor is None or valor == '':
        return ''
    return 'Sim' if valor else 'Não'


def esquema_da_casa(link, casa_url):
    """Troca o esquema/host do link pelos da casa (a API devolve `http://`)."""
    if not link:
        return ''
    partes, casa = urlparse(link), urlparse(casa_url)
    if partes.hostname == casa.hostname:
        return partes._replace(scheme=casa.scheme, netloc=casa.netloc).geturl()
    return link


# --- Extração pela página HTML ----------------------------------------------

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


# --- Extração pela API ------------------------------------------------------

class Consultas:
    """Nomes de tipo, regime e matérias anexadas, consultados na API da casa.

    Cada id é consultado uma vez por execução (cache). Uma consulta que falha
    deixa o campo vazio e gera um aviso; não derruba a matéria.
    """

    def __init__(self, cliente, casa_url):
        self.cliente = cliente
        self.base = casa_url.rstrip('/')
        self._cache = {}

    def _nome(self, caminho, campo):
        url = f'{self.base}/api/{caminho}/'
        if url not in self._cache:
            nome = ''
            resposta = self.cliente.get(url)
            if resposta.ok:
                try:
                    dados = resposta.json()
                    nome = limpar(dados.get(campo) or dados.get('__str__'))
                except (ValueError, AttributeError):
                    pass
            if not nome:
                log.warning('Não foi possível obter o nome em %s (%s)', url,
                            resposta.erro or 'resposta inesperada')
            self._cache[url] = nome
        return self._cache[url]

    def tipo(self, id_):
        return self._nome(f'materia/tipomaterialegislativa/{id_}', 'descricao') if id_ else ''

    def regime(self, id_):
        return self._nome(f'materia/regimetramitacao/{id_}', 'descricao') if id_ else ''

    def materia(self, id_):
        return self._nome(f'materia/materialegislativa/{id_}', '__str__') if id_ else ''


def url_api(casa_url, sapl_id):
    return f"{casa_url.rstrip('/')}/api/materia/materialegislativa/{sapl_id}/"


def extrair_api(dados, casa_url, consultas):
    """Campos de COLUNAS_DADOS a partir do JSON da API. Ignora `ip`, `user` etc."""
    anexadas = dados.get('anexadas') or []
    return {
        'Titulo': limpar(dados.get('__str__')),
        'Ementa': limpar(dados.get('ementa')),
        'Ano': limpar(dados.get('ano')),
        'Data': data_br(dados.get('data_apresentacao')),
        'Numero': limpar(dados.get('numero')),
        'Observacao': limpar(dados.get('observacao')),
        'Tipo de Materia Legislativa': consultas.tipo(dados.get('tipo')),
        'texto_original': esquema_da_casa(limpar(dados.get('texto_original')), casa_url),
        'Indexacao': limpar(dados.get('indexacao')),
        'Em Tramitacao': sim_nao(dados.get('em_tramitacao')),
        'Regime Tramitacao': consultas.regime(dados.get('regime_tramitacao')),
        'Materia Anexada': SEPARADOR.join(n for n in (consultas.materia(i) for i in anexadas) if n),
        'Resultado': limpar(dados.get('resultado')),
        'Data Publicacao': data_br(dados.get('data_publicacao')),
        'Numero Protocolo': limpar(dados.get('numero_protocolo')),
        'Ultima Atualizacao': data_hora_br(dados.get('data_ultima_atualizacao')),
    }


# --- Raspagem de uma matéria ------------------------------------------------

class Fontes:
    """Fonte de dados de cada casa: 'api' (padrão) ou 'html' (casa sem API).

    Uma casa só passa para 'html' enquanto a API dela nunca funcionou nesta
    execução. Depois que a API devolveu uma matéria, um 404 isolado (falha
    pontual do site) só manda aquela matéria para o HTML.
    """

    def __init__(self):
        self._por_host = {}
        self._consultas = {}
        self._api_confirmada = set()

    def de(self, casa_url):
        return self._por_host.get(host(casa_url), 'api')

    def confirmar_api(self, casa_url):
        self._api_confirmada.add(host(casa_url))

    def api_confirmada(self, casa_url):
        return host(casa_url) in self._api_confirmada

    def usar_html(self, casa_url, motivo):
        if self.api_confirmada(casa_url):
            log.warning('API de %s falhou para uma matéria (%s): só essa vai pelo HTML',
                        host(casa_url), motivo)
            return
        if self.de(casa_url) != 'html':
            log.info('Casa %s sem API de matérias (%s): usando as páginas HTML',
                     host(casa_url), motivo)
        self._por_host[host(casa_url)] = 'html'

    def consultas(self, cliente, casa_url):
        h = host(casa_url)
        if h not in self._consultas:
            self._consultas[h] = Consultas(cliente, casa_url)
        return self._consultas[h]


def _agora():
    return datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def linha_vazia(link):
    """Linha com COLUNAS_MATERIAS a partir de um item de links (COLUNAS_LINKS)."""
    linha = {c: '' for c in COLUNAS_MATERIAS}
    for c in COLUNAS_LINKS:
        linha[c] = link.get(c, '')
    return linha


def raspar_materia(link, cliente, fontes):
    """Raspa uma matéria e devolve a linha (COLUNAS_MATERIAS) com `status` ok ou erro.

    Tenta a API; se a casa não tiver API (404 ou resposta que não é JSON),
    passa a usar o HTML para essa casa (veja `Fontes`). Uma requisição que falha nunca é
    lida como se fosse a matéria: a linha sai com `status = erro` e o motivo.
    """
    casa = link['Link Casa']
    linha = linha_vazia(link)
    linha['raspada_em'] = _agora()

    if fontes.de(casa) == 'api':
        resposta = cliente.get(url_api(casa, link['sapl_id']))
        if resposta.ok:
            try:
                dados = resposta.json()
            except ValueError:
                dados = None
            if isinstance(dados, dict) and 'id' in dados:
                linha.update(extrair_api(dados, casa, fontes.consultas(cliente, casa)))
                linha.update(fonte='api', status='ok')
                fontes.confirmar_api(casa)
                return linha
            fontes.usar_html(casa, 'resposta não é JSON')
        elif resposta.status != 404:
            linha.update(status='erro', erro=resposta.erro)
            return linha
        # 404: pode ser casa sem API ou matéria apagada; o HTML decide

    resposta = cliente.get(link['Link Materia'])
    if not resposta.ok:
        linha.update(status='erro', erro=resposta.erro)
        return linha
    campos = extrair_html(resposta.texto, casa)
    if not campos['Titulo']:
        linha.update(status='erro', erro='página sem dados de matéria')
        return linha
    if fontes.de(casa) == 'api':
        fontes.usar_html(casa, 'API respondeu 404')
    linha.update(campos)
    linha.update(fonte='html', status='ok')
    return linha


# --- Etapa de raspagem e arquivo de links ------------------------------------

def salvar_links(links, caminho):
    """Grava a lista de links únicos (COLUNAS_LINKS), substituindo o arquivo."""
    with open(caminho, 'w', newline='', encoding='utf-8') as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_LINKS, extrasaction='ignore')
        escritor.writeheader()
        escritor.writerows(links)


def ler_links(caminho):
    return ler_csv(caminho, COLUNAS_LINKS)


def raspar_todas(links, cliente, estado, arquivo_materias, fontes=None):
    """Raspa as matérias que ainda não estão `ok` no estado.

    Cada matéria é gravada em `arquivo_materias` **antes** de o estado ser
    atualizado: se o programa cair entre as duas gravações, a matéria só é
    raspada de novo (a linha mais recente vale na tabela final).
    """
    fontes = fontes or Fontes()
    pendentes = [l for l in links if estado.status('materia', l['chave']) != 'ok']
    log.info('Matérias: %d a raspar, %d já raspadas', len(pendentes), len(links) - len(pendentes))
    arquivo = ArquivoCSV(arquivo_materias, COLUNAS_MATERIAS)
    try:
        for i, link in enumerate(pendentes, start=1):
            linha = raspar_materia(link, cliente, fontes)
            arquivo.anexar(linha)
            estado.registrar('materia', link['chave'], linha['status'], linha['erro'])
            detalhe = linha['Titulo'] if linha['status'] == 'ok' else f"ERRO: {linha['erro']}"
            log.info('Matéria %d de %d (%s): %s', i, len(pendentes), link['chave'], detalhe)
    finally:
        arquivo.fechar()
    return fontes
