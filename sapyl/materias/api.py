"""Extração dos dados de uma matéria pela API JSON do SAPL."""

from typing import Any

from sapyl import registro
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import SEPARADOR, Linha
from sapyl.estado import Cache
from sapyl.materias.valores import data_br, data_hora_br, esquema_da_casa, limpar, sim_nao

log = registro.logger('materias')


class Consultas:
    """Nomes de tipo, regime e matérias anexadas, consultados na API da casa.

    Cada id é consultado uma vez por execução. Os nomes obtidos vão para o
    `Cache` do projeto e valem nas próximas execuções; uma consulta que falha
    deixa o campo vazio, gera um aviso e não vai para o disco (é tentada de
    novo na próxima execução). Não derruba a matéria.
    """

    def __init__(self, cliente: ClienteSAPL, casa_url: str, cache: Cache | None = None) -> None:
        self.cliente = cliente
        self.base = casa_url.rstrip('/')
        self.cache = cache if cache is not None else Cache()
        self._falhas = set()
        self._respostas: dict[str, dict[str, Any]] = {}

    def _nome(self, caminho: str, campo: str) -> str:
        url = f'{self.base}/api/{caminho}/'
        guardado = self.cache.nome(url)
        if guardado is not None:
            return guardado
        if url not in self._falhas:
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
            if nome:
                self.cache.guardar_nome(url, nome)
                return nome
            self._falhas.add(url)
        return ''

    def _campo(self, caminho: str, campo: str) -> str:
        """Um campo de um objeto da API. O objeto é pedido uma vez por execução.

        Guardado no cache como `<url>#<campo>`, porque um mesmo objeto (ex.: o
        autor) dá mais de um campo (nome e tipo).
        """
        url = f'{self.base}/api/{caminho}/'
        chave = f'{url}#{campo}'
        guardado = self.cache.nome(chave)
        if guardado is not None:
            return guardado
        if url in self._falhas:
            return ''
        if url not in self._respostas:
            resposta = self.cliente.get(url)
            dados = None
            if resposta.ok:
                try:
                    dados = resposta.json()
                except ValueError:
                    dados = None
            if not isinstance(dados, dict):
                log.warning(
                    'Não foi possível obter %s (%s)', url, resposta.erro or 'resposta inesperada'
                )
                self._falhas.add(url)
                return ''
            self._respostas[url] = dados
        valor = limpar(self._respostas[url].get(campo))
        if valor:
            self.cache.guardar_nome(chave, valor)
        return valor

    def autor(self, id_: int | None) -> str:
        """'NOME (Tipo)' de um autor, como na página de autoria (ex.: 'Zé Lopes (Parlamentar)').

        O nome é o `__str__` da API, que inclui o cargo quando há (`nome - cargo`).
        """
        if not id_:
            return ''
        nome = self._campo(f'base/autor/{id_}', '__str__')
        tipo_id = self._campo(f'base/autor/{id_}', 'tipo')
        tipo = self._campo(f'base/tipoautor/{tipo_id}', '__str__') if tipo_id else ''
        if not nome:
            return ''
        return f'{nome} ({tipo})' if tipo else nome

    def status_tramitacao(self, id_: int | None) -> str:
        """Descrição de um status de tramitação."""
        return self._nome(f'materia/statustramitacao/{id_}', 'descricao') if id_ else ''

    def unidade(self, id_: int | None) -> str:
        """Nome de uma unidade de tramitação (ex.: 'Plenário da Câmara - PLEN')."""
        return self._nome(f'materia/unidadetramitacao/{id_}', '__str__') if id_ else ''

    def tipo(self, id_: int | None) -> str:
        """Nome do tipo de matéria (ex.: 'Projeto de Lei Ordinária')."""
        return self._nome(f'materia/tipomaterialegislativa/{id_}', 'descricao') if id_ else ''

    def regime(self, id_: int | None) -> str:
        """Nome do regime de tramitação."""
        return self._nome(f'materia/regimetramitacao/{id_}', 'descricao') if id_ else ''

    def materia(self, id_: int | None) -> str:
        """Título de outra matéria (usado nas matérias anexadas)."""
        return self._nome(f'materia/materialegislativa/{id_}', '__str__') if id_ else ''


def url_api(casa_url: str, sapl_id: str) -> str:
    """URL da matéria na API, com a barra final (sem ela, a API redireciona)."""
    return f'{casa_url.rstrip("/")}/api/materia/materialegislativa/{sapl_id}/'


def extrair_api(dados: dict[str, Any], casa_url: str, consultas: Consultas) -> Linha:
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
