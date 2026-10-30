"""Busca das palavras-chave no sistema de pesquisa de cada casa legislativa.

Para cada casa ativa e cada palavra, pede as páginas
`<casa>sistema/search/?page=N&q=<palavra>` até o servidor responder 404
(fim das páginas). De cada página, só os links de matérias são gravados, na
hora, em `<nome>_paginas_busca.csv` (o HTML não é guardado).

Uma busca que falha no meio (429 insistente, 5xx, timeout...) fica marcada
como `incompleta` no estado e aparece no resumo; ao retomar o projeto, ela é
refeita. Buscas `completa` não são repetidas.

`buscar_casa` faz as buscas de uma casa (usada por casa, várias ao mesmo
tempo); `buscar` faz as de todas, uma casa por vez.
"""

from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from sapyl import registro
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import COLUNAS_PAGINAS, ETAPA_BUSCA, Linha
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
    casa: str,
    palavra: str,
    cliente: ClienteSAPL,
    estado: Estado,
    paginas: ArquivoCSV,
    base: str | None = None,
    achados: list[Linha] | None = None,
) -> int:
    """Busca uma palavra numa casa, página a página. Devolve o nº de páginas gravadas.

    `base`: endereço para as requisições, se o site da casa redireciona (veja
    `url_final`). A casa continua identificada pelo endereço original.
    `achados`: se dada, recebe os links de matérias encontrados (como
    `links.raspar_paginas` os leria do arquivo).
    """
    chave = chave_busca(casa, palavra)
    base = base or casa
    pagina = 1
    while pagina <= MAX_PAGINAS:
        url = url_busca(base, palavra, pagina)
        resposta = cliente.get(url)
        if resposta.ok:
            encontrados = links_da_pagina(resposta.texto, casa, [base])
            paginas.anexar(
                {
                    'Casa': casa,
                    'Palavra': palavra,
                    'Pagina': pagina,
                    'links': ' '.join(encontrados),
                    'link': url,
                }
            )
            if achados is not None:
                achados += [
                    {'Link Materia': link, 'Link Casa': casa, 'Palavras': palavra}
                    for link in encontrados
                ]
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


def buscar_casa(
    casa: str,
    palavras: list[str],
    cliente: ClienteSAPL,
    estado: Estado,
    paginas: ArquivoCSV,
    base: str | None = None,
) -> list[Linha]:
    """Faz as buscas ainda não `completa` de uma casa. Devolve os links achados agora.

    Os links vêm na ordem das palavras e das páginas, com repetições (use
    `links.deduplicar_links`).
    """
    pendentes = [
        p for p in palavras if estado.status(ETAPA_BUSCA, chave_busca(casa, p)) != 'completa'
    ]
    achados: list[Linha] = []
    if pendentes:
        log.info('Busca em %s: %d palavra(s)', casa, len(pendentes))
    for palavra in pendentes:
        n = buscar_palavra(casa, palavra, cliente, estado, paginas, base, achados)
        log.info('  %s: %d página(s)', palavra, n)
    return achados


def enderecos_de_busca(casas: pd.DataFrame) -> dict[str, str]:
    """{url da casa: url_final} das casas cujo site redireciona."""
    if 'url_final' not in casas.columns:
        return {}
    return {u: f for u, f in zip(casas['url'], casas['url_final'], strict=True) if f}


def buscar(
    casas: pd.DataFrame,
    palavras: list[str],
    cliente: ClienteSAPL,
    estado: Estado,
    arquivo_paginas: str | Path,
) -> None:
    """Faz as buscas pendentes. `casas`: DataFrame com `url`, `ativa` e (opcional) `url_final`."""
    finais = enderecos_de_busca(casas)
    pendentes = buscas_pendentes(casas, palavras, estado)
    total_casas = len({c for c, _ in pendentes})
    arquivo = ArquivoCSV(arquivo_paginas, COLUNAS_PAGINAS)
    try:
        casa_atual, n_casa = None, 0
        for casa, palavra in pendentes:
            if casa != casa_atual:
                casa_atual, n_casa = casa, n_casa + 1
                log.info('Busca na casa %d de %d: %s', n_casa, total_casas, casa)
            paginas = buscar_palavra(casa, palavra, cliente, estado, arquivo, finais.get(casa))
            log.info('  %s: %d página(s)', palavra, paginas)
    finally:
        arquivo.fechar()
