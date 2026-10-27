"""Extração dos dados de uma matéria pela API JSON do SAPL."""

from sapyl import registro
from sapyl.colunas import SEPARADOR
from sapyl.materias.valores import data_br, data_hora_br, esquema_da_casa, limpar, sim_nao

log = registro.logger('materias')


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
                log.warning(
                    'Não foi possível obter o nome em %s (%s)',
                    url,
                    resposta.erro or 'resposta inesperada',
                )
            self._cache[url] = nome
        return self._cache[url]

    def tipo(self, id_):
        return self._nome(f'materia/tipomaterialegislativa/{id_}', 'descricao') if id_ else ''

    def regime(self, id_):
        return self._nome(f'materia/regimetramitacao/{id_}', 'descricao') if id_ else ''

    def materia(self, id_):
        return self._nome(f'materia/materialegislativa/{id_}', '__str__') if id_ else ''


def url_api(casa_url, sapl_id):
    return f'{casa_url.rstrip("/")}/api/materia/materialegislativa/{sapl_id}/'


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
