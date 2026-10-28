"""Busca das palavras-chave no sistema de pesquisa de cada casa legislativa.

Para cada casa ativa e cada palavra, pede as páginas
`<casa>sistema/search/?page=N&q=<palavra>` até o servidor responder 404
(fim das páginas). De cada página, só os links de matérias são gravados, na
hora, em `<nome>_paginas_busca.csv` (o HTML não é guardado).

Uma busca que falha no meio (429 insistente, 5xx, timeout...) fica marcada
como `incompleta` no estado e aparece no resumo; ao retomar o projeto, ela é
refeita. Buscas `completa` não são repetidas.
"""

from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from sapyl import registro
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import COLUNAS_PAGINAS, ETAPA_BUSCA
from sapyl.estado import ArquivoCSV, Estado
from sapyl.links import links_da_pagina

# Proteção contra paginação sem fim (Rio Branco, a maior do teste, tem ~400)
MAX_PAGINAS = 5000

log = registro.logger('busca')


def chave_busca(casa_url: str, palavra: str) -> str:
    """Chave de uma busca no estado: `<host>|<palavra>`."""
    return f'{urlparse(casa_url).hostname}|{palavra}'


def url_busca(casa_url: str, palavra: str, pagina: int) -> str:
    """URL de uma página de resultados da busca de `palavra` na casa."""
    return f'{casa_url}sistema/search/?page={pagina}&q={palavra}'


def buscas_pendentes(
    casas: pd.DataFrame, palavras: list[str], estado: Estado
) -> list[tuple[str, str]]:
    """(casa, palavra) das casas ativas cuja busca ainda não está `completa`."""
    return [
        (casa, palavra)
        for casa in casas[casas['ativa']]['url']
        for palavra in palavras
        if estado.status(ETAPA_BUSCA, chave_busca(casa, palavra)) != 'completa'
    ]


def buscar_palavra(
    casa: str, palavra: str, cliente: ClienteSAPL, estado: Estado, paginas: ArquivoCSV
) -> int:
    """Busca uma palavra numa casa, página a página. Devolve o nº de páginas gravadas."""
    chave = chave_busca(casa, palavra)
    pagina = 1
    while pagina <= MAX_PAGINAS:
        url = url_busca(casa, palavra, pagina)
        resposta = cliente.get(url)
        if resposta.ok:
            paginas.anexar(
                {
                    'Casa': casa,
                    'Palavra': palavra,
                    'Pagina': pagina,
                    'links': ' '.join(links_da_pagina(resposta.texto, casa)),
                    'link': url,
                }
            )
            pagina += 1
            continue
        if resposta.status == 404 and pagina > 1:
            estado.registrar(ETAPA_BUSCA, chave, 'completa')
            return pagina - 1
        # 404 já na primeira página não é "sem resultados" (isso volta 200):
        # a busca dessa casa não está funcionando.
        erro = (
            resposta.erro if pagina > 1 or resposta.status != 404 else 'HTTP 404 na primeira página'
        )
        log.warning('Busca incompleta em %s para %s (página %d): %s', casa, palavra, pagina, erro)
        estado.registrar(ETAPA_BUSCA, chave, 'incompleta', f'página {pagina}: {erro}')
        return pagina - 1
    estado.registrar(ETAPA_BUSCA, chave, 'incompleta', f'mais de {MAX_PAGINAS} páginas')
    return pagina - 1


def buscar(
    casas: pd.DataFrame,
    palavras: list[str],
    cliente: ClienteSAPL,
    estado: Estado,
    arquivo_paginas: str | Path,
) -> None:
    """Faz as buscas pendentes. `casas`: DataFrame com `url` e `ativa`."""
    pendentes = buscas_pendentes(casas, palavras, estado)
    total_casas = len({c for c, _ in pendentes})
    arquivo = ArquivoCSV(arquivo_paginas, COLUNAS_PAGINAS)
    try:
        casa_atual, n_casa = None, 0
        for casa, palavra in pendentes:
            if casa != casa_atual:
                casa_atual, n_casa = casa, n_casa + 1
                log.info('Busca na casa %d de %d: %s', n_casa, total_casas, casa)
            paginas = buscar_palavra(casa, palavra, cliente, estado, arquivo)
            log.info('  %s: %d página(s)', palavra, paginas)
    finally:
        arquivo.fechar()
