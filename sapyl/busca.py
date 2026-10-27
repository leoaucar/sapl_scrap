"""Busca das palavras-chave no sistema de pesquisa de cada casa legislativa.

Para cada casa ativa e cada palavra, pede as páginas
`<casa>sistema/search/?page=N&q=<palavra>` até o servidor responder 404
(fim das páginas). Cada página é gravada na hora no arquivo bruto do projeto.

Uma busca que falha no meio (429 insistente, 5xx, timeout...) fica marcada
como `incompleta` no estado e aparece no resumo; ao retomar o projeto, ela é
refeita. Buscas `completa` não são repetidas.
"""
from urllib.parse import urlparse

from sapyl.estado import ArquivoCSV
from sapyl import registro
from sapyl.colunas import COLUNAS_CRU, ETAPA_BUSCA

# Proteção contra paginação sem fim (Rio Branco, a maior do teste, tem ~400)
MAX_PAGINAS = 5000

log = registro.logger('busca')


def chave_busca(casa_url, palavra):
    return f'{urlparse(casa_url).hostname}|{palavra}'


def url_busca(casa_url, palavra, pagina):
    return f'{casa_url}sistema/search/?page={pagina}&q={palavra}'


def buscas_pendentes(casas, palavras, estado):
    """(casa, palavra) das casas ativas cuja busca ainda não está `completa`."""
    return [(casa, palavra)
            for casa in casas[casas['ativa']]['url']
            for palavra in palavras
            if estado.status(ETAPA_BUSCA, chave_busca(casa, palavra)) != 'completa']


def buscar_palavra(casa, palavra, cliente, estado, cru):
    """Busca uma palavra numa casa, página a página. Devolve o nº de páginas gravadas."""
    chave = chave_busca(casa, palavra)
    pagina = 1
    while pagina <= MAX_PAGINAS:
        url = url_busca(casa, palavra, pagina)
        resposta = cliente.get(url)
        if resposta.ok:
            cru.anexar({'Indice': '', 'Casa': casa, 'Palavra': palavra, 'Pagina': pagina,
                        'html': resposta.texto, 'link': url})
            pagina += 1
            continue
        if resposta.status == 404 and pagina > 1:
            estado.registrar(ETAPA_BUSCA, chave, 'completa')
            return pagina - 1
        # 404 já na primeira página não é "sem resultados" (isso volta 200):
        # a busca dessa casa não está funcionando.
        erro = resposta.erro if pagina > 1 or resposta.status != 404 else 'HTTP 404 na primeira página'
        log.warning('Busca incompleta em %s para %s (página %d): %s', casa, palavra, pagina, erro)
        estado.registrar(ETAPA_BUSCA, chave, 'incompleta', f'página {pagina}: {erro}')
        return pagina - 1
    estado.registrar(ETAPA_BUSCA, chave, 'incompleta', f'mais de {MAX_PAGINAS} páginas')
    return pagina - 1


def buscar(casas, palavras, cliente, estado, arquivo_cru):
    """Faz as buscas pendentes. `casas`: DataFrame com `url` e `ativa`."""
    pendentes = buscas_pendentes(casas, palavras, estado)
    total_casas = len({c for c, _ in pendentes})
    cru = ArquivoCSV(arquivo_cru, COLUNAS_CRU)
    try:
        casa_atual, n_casa = None, 0
        for casa, palavra in pendentes:
            if casa != casa_atual:
                casa_atual, n_casa = casa, n_casa + 1
                log.info('Busca na casa %d de %d: %s', n_casa, total_casas, casa)
            paginas = buscar_palavra(casa, palavra, cliente, estado, cru)
            log.info('  %s: %d página(s)', palavra, paginas)
    finally:
        cru.fechar()
