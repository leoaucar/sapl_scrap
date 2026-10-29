"""Peças de apoio para os testes: relógio falso, sessão HTTP falsa e fixtures.

Nenhum teste acessa a rede (veja `bloquear_rede` em conftest.py). As respostas
HTTP são roteiros definidos em cada teste com `SessaoFalsa.responder`.
"""

import json
import pathlib
import threading

import requests

PASTA_FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


def ler_fixture(caminho):
    """Texto de um arquivo em tests/fixtures/ (caminho relativo a essa pasta)."""
    return (PASTA_FIXTURES / caminho).read_text(encoding='utf-8')


class RelogioFalso:
    """Relógio que só anda quando alguém "dorme". Nada espera de verdade.

    Com várias threads, o tempo é um só: cada "sono" de qualquer uma o faz andar.
    """

    def __init__(self, inicio=1000.0):
        self.t = inicio
        self.esperas = []
        self._trava = threading.Lock()

    def agora(self):
        return self.t

    def dormir(self, segundos):
        with self._trava:
            self.esperas.append(segundos)
            self.t += max(0, segundos)


class RespostaFalsa:
    """Imita o pedaço de `requests.Response` que o código usa."""

    def __init__(
        self, status=200, texto='', conteudo=None, headers=None, url='', falhar_no_meio=False
    ):
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
            yield self.content[i : i + chunk_size]
            if self.falhar_no_meio:
                raise requests.ConnectionError('conexão caiu no meio do download')

    def close(self):
        self.fechada = True


class SessaoFalsa:
    """Sessão HTTP com respostas roteirizadas por URL.

    `responder(url, ...)` enfileira respostas para a URL; a última da fila se
    repete. `responder(url, erro=requests.Timeout())` faz a chamada lançar a
    exceção; `url_final=...` imita um redirecionamento (a resposta vem de outra
    URL). `rota(funcao)` cobre URLs não roteirizadas: `funcao(url)` devolve
    uma `RespostaFalsa` ou None. URL sem roteiro faz o teste falhar. Pode ser
    usada por várias threads ao mesmo tempo.
    """

    def __init__(self):
        self._trava = threading.RLock()
        self._filas = {}
        self._rotas = []
        self.pedidos = []  # URLs, na ordem
        self.chamadas = []  # (url, kwargs)

    def responder(
        self,
        url,
        status=200,
        texto='',
        fixture=None,
        json_dados=None,
        conteudo=None,
        headers=None,
        erro=None,
        falhar_no_meio=False,
        url_final=None,
    ):
        if fixture is not None:
            texto = ler_fixture(fixture)
        if json_dados is not None:
            texto = json.dumps(json_dados)
        item = (
            erro
            if erro is not None
            else RespostaFalsa(status, texto, conteudo, headers, url_final or url, falhar_no_meio)
        )
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
        with self._trava:
            self.pedidos.append(url)
            self.chamadas.append((url, kwargs))
            fila = self._filas.get(url)
            item = (fila.pop(0) if len(fila) > 1 else fila[0]) if fila else None
        if item is not None:
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

    Autoria e tramitação: `autorias={id: [id do autor...]}` e
    `tramitacoes={id: [trâmite...]}` alimentam as listas da API;
    `nomes={('autor', '145'): dados}` (ou `tipoautor`, `statustramitacao`...)
    as consultas de nomes; `html={'<id>/autoria': página}` as abas HTML.
    """

    def __init__(self):
        self._casas = {}
        self._falhas = {}
        self._trava = threading.Lock()

    def casa(
        self,
        url,
        buscas=None,
        api=None,
        html=None,
        pdfs=None,
        ativa=True,
        nomes=None,
        autorias=None,
        tramitacoes=None,
    ):
        from urllib.parse import urlparse

        self._casas[urlparse(url).hostname] = {
            'url': url,
            'buscas': buscas or {},
            'api': api,
            'html': html or {},
            'pdfs': pdfs or {},
            'ativa': ativa,
            'nomes': nomes or {},
            'autorias': autorias or {},
            'tramitacoes': tramitacoes or {},
        }
        return self

    def falhar(self, url, *status):
        self._falhas.setdefault(url, []).extend(status)
        return self

    @staticmethod
    def _conteudo(item):
        if isinstance(item, (dict, list)):
            return json.dumps(item)
        if (
            isinstance(item, str)
            and item.endswith(('.html', '.json'))
            and '/' in item
            and '<' not in item
        ):
            return ler_fixture(item)
        return item

    def __call__(self, url):
        import re
        from urllib.parse import urlparse

        partes = urlparse(url)
        casa = self._casas.get(partes.hostname)
        if casa is None:
            return None
        with self._trava:
            status = self._falhas[url].pop(0) if self._falhas.get(url) else None
        if status is not None:
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
        if caminho in ('/api/materia/autoria/', '/api/materia/tramitacao/'):
            if casa['api'] is None:
                return RespostaFalsa(404, 'sem api')
            from urllib.parse import parse_qs

            id_ = parse_qs(partes.query)['materia'][0]
            if caminho == '/api/materia/autoria/':
                itens = [{'autor': a, 'materia': int(id_)} for a in casa['autorias'].get(id_, [])]
            else:
                itens = casa['tramitacoes'].get(id_, [])
            return RespostaFalsa(
                200, json.dumps({'pagination': {'links': {'next': None}}, 'results': itens})
            )
        achado = re.match(r'^/api/base/(\w+)/(\d+)/$', caminho)
        if achado:
            if casa['api'] is None:
                return RespostaFalsa(404, 'sem api')
            dados = casa['nomes'].get(achado.groups())
            if dados is None:
                return RespostaFalsa(404, 'não existe')
            return RespostaFalsa(200, self._conteudo(dados))
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
            if not isinstance(nome, str) or nome.endswith('.json'):
                return RespostaFalsa(200, self._conteudo(nome))
            return RespostaFalsa(
                200, json.dumps({'id': int(id_), '__str__': nome, 'descricao': nome})
            )
        achado = re.match(r'^/materia/(\d+(?:/autoria|/tramitacao)?)$', caminho)
        if achado:
            pagina = casa['html'].get(achado.group(1))
            if pagina is None:
                return RespostaFalsa(404, 'não existe')
            return RespostaFalsa(200, self._conteudo(pagina))
        achado = re.match(r'^/media/sapl/public/materialegislativa/\d+/(\d+)/', caminho)
        if achado and achado.group(1) in casa['pdfs']:
            return RespostaFalsa(200, conteudo=casa['pdfs'][achado.group(1)])
        return RespostaFalsa(404, 'não existe')


# Projeto de exemplo da Fase 1 (tests/fixtures/projeto_fase1/, veja o README
# das fixtures). O mesmo SAPL falso serve para gerar a pasta e para retomá-la.
RB_FASE1 = 'https://sapl.riobranco.ac.leg.br/'
CV_FASE1 = 'https://sapl.cascavel.pr.leg.br/'
PALAVRAS_FASE1 = ['plano diretor', 'orçamento, emenda impositiva']
FALHA_FASE1 = f'{RB_FASE1}api/materia/materialegislativa/44086/'


def sapl_fase1(falhar=True):
    """Rio Branco (com API) e Cascavel (só HTML), 4 matérias cada.

    Com `falhar=True`, a matéria 44086 de Rio Branco responde 503 nas 4
    tentativas e fica com status `erro` (como ficou na pasta gravada).
    """
    import copy

    rb, cv = 'sapl/sapl.riobranco.ac.leg.br/', 'sapl/sapl.cascavel.pr.leg.br/'
    p, o = '"plano+diretor"', '"orçamento"+"emenda+impositiva"'

    def api_minima(sapl_id, titulo):
        dados = copy.deepcopy(json.loads(ler_fixture(rb + 'api_materia_34049.json')))
        dados.update(id=int(sapl_id), __str__=titulo, anexadas=[], texto_original=None)
        return dados

    falso = SaplFalso()
    falso.casa(
        RB_FASE1,
        buscas={p: [rb + 'busca_p1.html'], o: [rb + 'busca_vazia.html']},
        api={
            '34049': rb + 'api_materia_34049.json',
            '46496': rb + 'api_materia_46496.json',
            '37559': api_minima('37559', 'Projeto de Lei Complementar nº 26 de 2025'),
            '44086': api_minima('44086', 'Indicação nº 1 de 2026'),
        },
        nomes={
            ('tipomaterialegislativa', '1'): 'Projeto de Lei Ordinária',
            ('tipomaterialegislativa', '15'): 'Veto',
            ('regimetramitacao', '1'): 'Ordinária',
        },
        pdfs={'34049': b'%PDF-34049', '46496': b'%PDF-46496'},
    )
    falso.casa(
        CV_FASE1,
        api=None,
        buscas={p: [cv + 'busca_p1.html'], o: [cv + 'busca_vazia.html']},
        html={
            '38415': cv + 'materia_38415.html',
            '43301': cv + 'materia_43301.html',
            '43300': 'sinteticas/materia_sem_pdf.html',
            '42263': 'sinteticas/materia_sem_data.html',
        },
        pdfs={'38415': b'%PDF-38415'},
    )
    if falhar:
        falso.falhar(FALHA_FASE1, 503, 503, 503, 503)
    return falso
