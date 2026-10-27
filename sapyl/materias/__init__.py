"""Matérias legislativas: raspagem de cada matéria e etapa de raspagem.

Os dados vêm da API JSON do SAPL (`/api/materia/materialegislativa/<id>/`,
em `api.py`) quando a casa tem a API, ou da página HTML da matéria (versões
antigas do SAPL, em `html.py`). As duas fontes produzem as mesmas colunas
(`COLUNAS_DADOS`).
"""

from datetime import datetime
from pathlib import Path

from sapyl import registro
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import COLUNAS_LINKS, COLUNAS_MATERIAS, ETAPA_MATERIA, Linha
from sapyl.estado import ArquivoCSV, Estado
from sapyl.links import host
from sapyl.materias.api import Consultas, extrair_api, url_api
from sapyl.materias.html import extrair_html

__all__ = [
    'Consultas',
    'Fontes',
    'extrair_api',
    'extrair_html',
    'linha_vazia',
    'raspar_materia',
    'raspar_todas',
    'url_api',
]

log = registro.logger('materias')


class Fontes:
    """Fonte de dados de cada casa: 'api' (padrão) ou 'html' (casa sem API).

    Uma casa só passa para 'html' enquanto a API dela nunca funcionou nesta
    execução. Depois que a API devolveu uma matéria, um 404 isolado (falha
    pontual do site) só manda aquela matéria para o HTML.
    """

    def __init__(self) -> None:
        self._por_host = {}
        self._consultas = {}
        self._api_confirmada = set()

    def de(self, casa_url: str) -> str:
        """Fonte atual da casa: 'api' ou 'html'."""
        return self._por_host.get(host(casa_url), 'api')

    def confirmar_api(self, casa_url: str) -> None:
        """Marca que a API da casa já devolveu uma matéria nesta execução."""
        self._api_confirmada.add(host(casa_url))

    def api_confirmada(self, casa_url: str) -> bool:
        """Se a API da casa já funcionou nesta execução."""
        return host(casa_url) in self._api_confirmada

    def usar_html(self, casa_url: str, motivo: str) -> None:
        """Passa a casa para o HTML, a menos que a API dela já tenha funcionado."""
        if self.api_confirmada(casa_url):
            log.warning(
                'API de %s falhou para uma matéria (%s): só essa vai pelo HTML',
                host(casa_url),
                motivo,
            )
            return
        if self.de(casa_url) != 'html':
            log.info(
                'Casa %s sem API de matérias (%s): usando as páginas HTML', host(casa_url), motivo
            )
        self._por_host[host(casa_url)] = 'html'

    def consultas(self, cliente: ClienteSAPL, casa_url: str) -> Consultas:
        """Consultas de nomes da casa (uma instância por casa, com cache)."""
        h = host(casa_url)
        if h not in self._consultas:
            self._consultas[h] = Consultas(cliente, casa_url)
        return self._consultas[h]


def _agora() -> str:
    return datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def linha_vazia(link: Linha) -> Linha:
    """Linha com COLUNAS_MATERIAS a partir de um item de links (COLUNAS_LINKS)."""
    linha = {c: '' for c in COLUNAS_MATERIAS}
    for c in COLUNAS_LINKS:
        linha[c] = link.get(c, '')
    return linha


def raspar_materia(link: Linha, cliente: ClienteSAPL, fontes: Fontes) -> Linha:
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


def raspar_todas(
    links: list[Linha],
    cliente: ClienteSAPL,
    estado: Estado,
    arquivo_materias: str | Path,
    fontes: Fontes | None = None,
) -> Fontes:
    """Raspa as matérias que ainda não estão `ok` no estado.

    Cada matéria é gravada em `arquivo_materias` **antes** de o estado ser
    atualizado: se o programa cair entre as duas gravações, a matéria só é
    raspada de novo (a linha mais recente vale na tabela final).
    """
    fontes = fontes or Fontes()
    pendentes = [item for item in links if estado.status(ETAPA_MATERIA, item['chave']) != 'ok']
    log.info('Matérias: %d a raspar, %d já raspadas', len(pendentes), len(links) - len(pendentes))
    arquivo = ArquivoCSV(arquivo_materias, COLUNAS_MATERIAS)
    try:
        for i, link in enumerate(pendentes, start=1):
            linha = raspar_materia(link, cliente, fontes)
            arquivo.anexar(linha)
            estado.registrar(ETAPA_MATERIA, link['chave'], linha['status'], linha['erro'])
            detalhe = linha['Titulo'] if linha['status'] == 'ok' else f'ERRO: {linha["erro"]}'
            log.info('Matéria %d de %d (%s): %s', i, len(pendentes), link['chave'], detalhe)
    finally:
        arquivo.fechar()
    return fontes
