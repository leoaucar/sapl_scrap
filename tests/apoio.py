"""Peças de apoio para os testes: relógio falso, sessão HTTP falsa e fixtures.

Nenhum teste acessa a rede (veja `bloquear_rede` em conftest.py). As respostas
HTTP são roteiros definidos em cada teste com `SessaoFalsa.responder`.
"""
import json
import pathlib

import requests

PASTA_FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


def ler_fixture(caminho):
    """Texto de um arquivo em tests/fixtures/ (caminho relativo a essa pasta)."""
    return (PASTA_FIXTURES / caminho).read_text(encoding='utf-8')


class RelogioFalso:
    """Relógio que só anda quando alguém "dorme". Nada espera de verdade."""

    def __init__(self, inicio=1000.0):
        self.t = inicio
        self.esperas = []

    def agora(self):
        return self.t

    def dormir(self, segundos):
        self.esperas.append(segundos)
        self.t += max(0, segundos)


class RespostaFalsa:
    """Imita o pedaço de `requests.Response` que o código usa."""

    def __init__(self, status=200, texto='', conteudo=None, headers=None,
                 url='', falhar_no_meio=False):
        self.status_code = status
        self.headers = dict(headers or {})
        self.url = url
        self._texto = texto
        self.content = conteudo if conteudo is not None else texto.encode('utf-8')
        self.falhar_no_meio = falhar_no_meio
        self.fechada = False

    @property
    def text(self):
        return self._texto

    def json(self):
        return json.loads(self._texto)

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]
            if self.falhar_no_meio:
                raise requests.ConnectionError('conexão caiu no meio do download')

    def close(self):
        self.fechada = True


class SessaoFalsa:
    """Sessão HTTP com respostas roteirizadas por URL.

    `responder(url, ...)` enfileira respostas para a URL; a última da fila se
    repete. `responder(url, erro=requests.Timeout())` faz a chamada lançar a
    exceção. `rota(funcao)` cobre URLs não roteirizadas: `funcao(url)` devolve
    uma `RespostaFalsa` ou None. URL sem roteiro faz o teste falhar.
    """

    def __init__(self):
        self._filas = {}
        self._rotas = []
        self.pedidos = []      # URLs, na ordem
        self.chamadas = []     # (url, kwargs)

    def responder(self, url, status=200, texto='', fixture=None, json_dados=None,
                  conteudo=None, headers=None, erro=None, falhar_no_meio=False):
        if fixture is not None:
            texto = ler_fixture(fixture)
        if json_dados is not None:
            texto = json.dumps(json_dados)
        item = erro if erro is not None else RespostaFalsa(
            status, texto, conteudo, headers, url, falhar_no_meio)
        self._filas.setdefault(url, []).append(item)
        return self

    def limpar(self, url):
        """Descarta as respostas roteirizadas de `url` (para trocar o roteiro)."""
        self._filas.pop(url, None)
        return self

    def rota(self, funcao):
        self._rotas.append(funcao)
        return self

    def get(self, url, **kwargs):
        self.pedidos.append(url)
        self.chamadas.append((url, kwargs))
        fila = self._filas.get(url)
        if fila:
            item = fila.pop(0) if len(fila) > 1 else fila[0]
            if isinstance(item, BaseException):
                raise item
            return item
        for funcao in self._rotas:
            resposta = funcao(url)
            if resposta is not None:
                return resposta
        raise AssertionError(f'URL sem resposta roteirizada no teste: {url}')

    def contar(self, trecho):
        """Quantos pedidos continham `trecho` na URL."""
        return sum(trecho in u for u in self.pedidos)


def roteiro(*respostas):
    """Função de entrada que devolve as respostas em ordem e registra as perguntas."""
    fila = list(respostas)
    perguntas = []

    def ler(texto=''):
        perguntas.append(texto)
        return fila.pop(0)
    ler.perguntas = perguntas
    return ler


class SaplFalso:
    """Rota para `SessaoFalsa.rota` que imita várias casas SAPL ao mesmo tempo.

    `casa(url, buscas={palavra: [página1, página2...]}, api={id: dados}, html={id: página},
    pdfs={id: bytes})`: cada página/dado pode ser o caminho de uma fixture ou o
    próprio conteúdo. `api=None` imita uma casa sem API (404). Páginas de busca
    além das definidas respondem 404 (fim). `falhar(url, 503, 429...)` faz a URL
    responder esses status, um por chamada, antes da resposta normal.
    """

    def __init__(self):
        self._casas = {}
        self._falhas = {}

    def casa(self, url, buscas=None, api=None, html=None, pdfs=None, ativa=True, nomes=None):
        from urllib.parse import urlparse
        self._casas[urlparse(url).hostname] = {
            'url': url, 'buscas': buscas or {}, 'api': api, 'html': html or {},
            'pdfs': pdfs or {}, 'ativa': ativa, 'nomes': nomes or {}}
        return self

    def falhar(self, url, *status):
        self._falhas.setdefault(url, []).extend(status)
        return self

    @staticmethod
    def _conteudo(item):
        if isinstance(item, (dict, list)):
            return json.dumps(item)
        if isinstance(item, str) and item.endswith(('.html', '.json')) and '/' in item and '<' not in item:
            return ler_fixture(item)
        return item

    def __call__(self, url):
        import re
        from urllib.parse import urlparse
        partes = urlparse(url)
        casa = self._casas.get(partes.hostname)
        if casa is None:
            return None
        if self._falhas.get(url):
            status = self._falhas[url].pop(0)
            return RespostaFalsa(status, '', headers={'Retry-After': '60'} if status == 429 else {})
        caminho = partes.path
        if caminho == '/':
            return RespostaFalsa(200 if casa['ativa'] else 500, 'início')
        if caminho == '/sistema/search/':
            achado = re.match(r'page=(\d+)&q=(.*)$', partes.query)
            paginas = casa['buscas'].get(achado.group(2), [])
            n = int(achado.group(1))
            if n <= len(paginas):
                return RespostaFalsa(200, self._conteudo(paginas[n - 1]))
            return RespostaFalsa(404, 'fim')
        achado = re.match(r'^/api/materia/(\w+)/(\d+)/$', caminho)
        if achado:
            recurso, id_ = achado.groups()
            if casa['api'] is None:
                return RespostaFalsa(404, 'sem api')
            if recurso == 'materialegislativa':
                dados = casa['api'].get(id_)
                if dados is None:
                    return RespostaFalsa(404, 'não existe')
                return RespostaFalsa(200, self._conteudo(dados))
            nome = casa['nomes'].get((recurso, id_), f'{recurso} {id_}')
            return RespostaFalsa(200, json.dumps({'id': int(id_), '__str__': nome, 'descricao': nome}))
        achado = re.match(r'^/materia/(\d+)$', caminho)
        if achado:
            pagina = casa['html'].get(achado.group(1))
            if pagina is None:
                return RespostaFalsa(404, 'não existe')
            return RespostaFalsa(200, self._conteudo(pagina))
        achado = re.match(r'^/media/sapl/public/materialegislativa/\d+/(\d+)/', caminho)
        if achado and achado.group(1) in casa['pdfs']:
            return RespostaFalsa(200, conteudo=casa['pdfs'][achado.group(1)])
        return RespostaFalsa(404, 'não existe')
