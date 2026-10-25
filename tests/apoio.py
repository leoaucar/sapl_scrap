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
