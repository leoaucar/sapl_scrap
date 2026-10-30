"""Acrescenta as colunas Autoria e Tramite a uma planilha de resultados.

É a opção 3 do menu do programa (`sapyl`): a entrada é o resultado final de
um projeto ou qualquer CSV com a coluna `Link Materia`. A planilha de entrada
não é alterada: o resultado vai para `<entrada>_autoria_tramitacao.csv`, ao
lado dela. O progresso fica em `<entrada>_autoria_tramitacao_estado.csv`, e
uma execução interrompida continua de onde parou.

- `Autoria`: autores da matéria, separados por '; ' (ex.: "PEDRO LONGO (Parlamentar)").
- `Tramite`: última tramitação, "<data> | <unidade local> | <unidade destino> | <status>".
- `status_autoria`, `status_tramitacao`: `ok` ou `erro`; `erro` traz o motivo.
- `fonte_autoria`: `api` ou `html` (de onde vieram os dados).

Os dados vêm da API do SAPL (`/api/materia/autoria/?materia=<id>` e
`/api/materia/tramitacao/?materia=<id>`, com os nomes de autores, unidades e
status consultados uma vez e guardados), ou das abas HTML da matéria nas
casas sem API. As duas fontes dão o mesmo texto.

As requisições passam pelo mesmo cliente do raspador (limite de 35 por
minuto por site, retentativas em 429/5xx).
"""

import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from bs4 import BeautifulSoup

from sapyl import registro
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import COLUNAS_AUTORIA, COLUNAS_AUTORIA_PARCIAL, ETAPA_AUTORIA, SEPARADOR, Linha
from sapyl.estado import ArquivoCSV, Estado, ler_csv
from sapyl.links import chave, no_endereco, normalizar_link
from sapyl.materias import Fontes
from sapyl.materias.api import Consultas
from sapyl.materias.valores import data_br, esquema_da_casa
from sapyl.padroes import Mapear, em_sequencia

SUFIXO_SAIDA = '_autoria_tramitacao'
log = registro.logger('autoria')


# Páginas de uma lista da API que seguimos, no máximo (cada uma tem até 100 itens)
MAX_PAGINAS_API = 20


def link_base(link: object) -> str:
    """Link da matéria sem `/ta` nem barra final."""
    return re.sub(r'/ta/?$', '', str(link).strip()).rstrip('/')


def casa_do_link(link: str) -> str:
    """`https://sapl.x.leg.br/materia/1` -> `https://sapl.x.leg.br/`."""
    partes = urlparse(str(link).strip())
    return f'{partes.scheme}://{partes.netloc}/'


def ler_tabela(html: str) -> list[dict[str, str]]:
    """Linhas da primeira tabela da página, como dicts {cabeçalho: texto}."""
    tabela = BeautifulSoup(html, 'html.parser').find('table')
    if tabela is None:
        return []
    cabecalhos = [th.get_text(' ', strip=True) for th in tabela.find_all('th')]
    linhas = []
    for tr in tabela.find_all('tr'):
        celulas = [' '.join(td.get_text(' ').split()) for td in tr.find_all('td')]
        if celulas:
            linhas.append(dict(zip(cabecalhos, celulas, strict=False)))
    return linhas


# --- Pelas páginas HTML (casas sem API) ---------------------------------------


def autoria_html(link: str, cliente: ClienteSAPL) -> tuple[str, str]:
    """(texto, erro) pela aba de autoria. Texto: 'AUTOR (Descrição); ...'."""
    resposta = cliente.get(link_base(link) + '/autoria')
    if not resposta.ok:
        return '', resposta.erro
    autores = []
    for linha in ler_tabela(resposta.texto):
        autor = linha.get('Autor', '')
        descricao = linha.get('Descrição', '')
        if autor:
            autores.append(f'{autor} ({descricao})' if descricao else autor)
    return SEPARADOR.join(autores), ''


def tramitacao_html(link: str, cliente: ClienteSAPL) -> tuple[str, str]:
    """(texto, erro) pela aba de tramitação: a mais recente (a primeira da tabela)."""
    resposta = cliente.get(link_base(link) + '/tramitacao')
    if not resposta.ok:
        return '', resposta.erro
    linhas = ler_tabela(resposta.texto)
    if not linhas:
        return '', ''
    ultima = linhas[0]
    campos = ['Data Tramitação', 'Unidade Local', 'Unidade Destino', 'Status']
    return ' | '.join(ultima.get(c, '') for c in campos), ''


# --- Pela API ---------------------------------------------------------------


def _lista_api(url: str, base: str, cliente: ClienteSAPL, paginas: int) -> tuple[str, object]:
    """('ok', itens) | ('sem_api', motivo) | ('erro', motivo) de uma lista da API.

    `sem_api`: 404 ou resposta que não é JSON (casa sem API: vale o HTML).
    """
    itens: list[dict] = []
    for _ in range(paginas):
        resposta = cliente.get(url)
        if not resposta.ok:
            if resposta.status == 404 and not itens:
                return 'sem_api', 'API respondeu 404'
            return 'erro', resposta.erro
        try:
            dados = resposta.json()
        except ValueError:
            dados = None
        if not isinstance(dados, dict) or not isinstance(dados.get('results'), list):
            return (
                ('sem_api', 'resposta não é JSON') if not itens else ('erro', 'resposta inesperada')
            )
        itens += dados['results']
        proxima = (dados.get('pagination') or {}).get('links', {}).get('next')
        if not proxima:
            break
        url = esquema_da_casa(proxima, base)
    return 'ok', itens


def autoria_api(
    base: str, sapl_id: str, cliente: ClienteSAPL, consultas: Consultas
) -> tuple[str, object]:
    """('ok', texto) | ('sem_api', motivo) | ('erro', motivo). Texto: 'NOME (Tipo); ...'."""
    url = f'{base.rstrip("/")}/api/materia/autoria/?materia={sapl_id}'
    situacao, resultado = _lista_api(url, base, cliente, MAX_PAGINAS_API)
    if situacao != 'ok':
        return situacao, resultado
    autores = [consultas.autor(item.get('autor')) for item in resultado]
    return 'ok', SEPARADOR.join(a for a in autores if a)


def tramitacao_api(
    base: str, sapl_id: str, cliente: ClienteSAPL, consultas: Consultas
) -> tuple[str, object]:
    """('ok', texto) | ('sem_api', motivo) | ('erro', motivo) do trâmite mais recente.

    A API lista a tramitação da mais nova para a mais antiga (como a página).
    Texto: 'dd/mm/aaaa | unidade local | unidade destino | status'.
    """
    url = f'{base.rstrip("/")}/api/materia/tramitacao/?materia={sapl_id}'
    situacao, resultado = _lista_api(url, base, cliente, 1)
    if situacao != 'ok':
        return situacao, resultado
    if not resultado:
        return 'ok', ''
    ultima = resultado[0]
    partes = [
        data_br(ultima.get('data_tramitacao')),
        consultas.unidade(ultima.get('unidade_tramitacao_local')),
        consultas.unidade(ultima.get('unidade_tramitacao_destino')),
        consultas.status_tramitacao(ultima.get('status')),
    ]
    return 'ok', ' | '.join(partes)


# --- Uma matéria ------------------------------------------------------------


def raspar_autoria(link_materia: str, cliente: ClienteSAPL, fontes: Fontes) -> Linha:
    """Autoria e último trâmite de uma matéria (COLUNAS_AUTORIA), pela API ou pelo HTML.

    Mesma regra das matérias (veja `Fontes`): a API primeiro; numa casa sem
    API (404 ou resposta que não é JSON), passa para as páginas HTML. Uma
    falha nunca vira texto vazio em silêncio: o status fica `erro`, com o motivo.
    """
    casa = casa_do_link(link_materia)
    base = fontes.base(casa)
    normal = normalizar_link(casa, link_materia)
    sapl_id = normal[1] if normal else ''
    link_pagina = no_endereco(link_base(link_materia), casa, base)
    usadas = []

    def parte(pela_api, pelo_html):
        if sapl_id and fontes.de(casa) == 'api':
            situacao, resultado = pela_api(base, sapl_id, cliente, fontes.consultas(cliente, casa))
            if situacao == 'ok':
                fontes.confirmar_api(casa)
                usadas.append('api')
                return resultado, ''
            if situacao == 'erro':
                usadas.append('api')
                return '', resultado
            fontes.usar_html(casa, resultado)
        usadas.append('html')
        return pelo_html(link_pagina, cliente)

    autoria, erro_a = parte(autoria_api, autoria_html)
    tramite, erro_t = parte(tramitacao_api, tramitacao_html)
    erros = [e for e in (erro_a and f'autoria: {erro_a}', erro_t and f'tramitação: {erro_t}') if e]
    return {
        'Autoria': autoria,
        'Tramite': tramite,
        'status_autoria': 'erro' if erro_a else 'ok',
        'status_tramitacao': 'erro' if erro_t else 'ok',
        'erro_autoria_tramitacao': SEPARADOR.join(erros),
        'fonte_autoria': usadas[0] if len(set(usadas)) == 1 else '+'.join(usadas),
    }


def arquivos_de_saida(entrada: str | Path) -> tuple[Path, Path, Path]:
    """(saída, parcial, estado) ao lado da planilha de entrada."""
    entrada = Path(entrada)
    base = entrada.with_name(entrada.stem + SUFIXO_SAIDA)
    return (
        base.with_suffix('.csv'),
        base.with_name(base.name + '_parcial.csv'),
        base.with_name(base.name + '_estado.csv'),
    )


def chave_do_link(link: object) -> str | None:
    """Chave `<host>/<sapl_id>` de um link de matéria, ou None se não for um."""
    casa = casa_do_link(str(link))
    normal = normalizar_link(casa, link)
    return chave(casa, normal[1]) if normal else None


def processar(
    entrada: str | Path,
    cliente: ClienteSAPL,
    fontes: Fontes | None = None,
    mapear: Mapear = em_sequencia,
) -> tuple[Path, Counter[str]]:
    """Busca autoria e tramitação das matérias de uma planilha e grava uma cópia com elas.

    A planilha precisa da coluna `Link Materia` e nunca é alterada. Cada
    matéria é gravada no arquivo parcial **antes** do estado; uma execução
    interrompida, rodada de novo, só busca o que falta ou falhou. No fim, a
    linha mais recente de cada matéria é juntada à planilha, pela chave, em
    `<entrada>_autoria_tramitacao.csv`. Devolve (saída, contagens por status).

    As matérias são agrupadas por casa; `mapear` diz como rodar as casas
    (padrão: uma por vez; o programa roda várias ao mesmo tempo).
    """
    dados = pd.read_csv(entrada, dtype=str, keep_default_na=False)
    dados = dados.drop(columns=[c for c in dados.columns if c.startswith('Unnamed')])
    if 'Link Materia' not in dados.columns:
        raise ValueError(f'{entrada} não tem a coluna "Link Materia"')
    saida, parcial, arquivo_estado = arquivos_de_saida(entrada)
    chaves = [chave_do_link(link) for link in dados['Link Materia']]
    unicas = {}
    for k, link in zip(chaves, dados['Link Materia'], strict=True):
        if k is not None and k not in unicas:
            unicas[k] = link

    fontes = fontes or Fontes()
    estado = Estado(arquivo_estado)
    arquivo = ArquivoCSV(parcial, COLUNAS_AUTORIA_PARCIAL)
    try:
        pendentes = [
            (k, link) for k, link in unicas.items() if estado.status(ETAPA_AUTORIA, k) != 'ok'
        ]
        log.info(
            'Autoria e tramitação: %d matérias a buscar, %d já feitas',
            len(pendentes),
            len(unicas) - len(pendentes),
        )
        por_casa: dict[str, list[tuple[str, str]]] = {}
        for k, link in pendentes:
            por_casa.setdefault(casa_do_link(link), []).append((k, link))

        def da_casa(casa: str) -> None:
            itens = por_casa[casa]
            for i, (k, link) in enumerate(itens, start=1):
                linha = raspar_autoria(link, cliente, fontes)
                arquivo.anexar({'chave': k, **linha})
                erro = linha['erro_autoria_tramitacao']
                estado.registrar(ETAPA_AUTORIA, k, 'erro' if erro else 'ok', erro)
                registro.andamento(
                    log,
                    registro.AUTORIA,
                    i,
                    len(itens),
                    'Autoria e tramitação %d de %d (%s): %s',
                    i,
                    len(itens),
                    k,
                    erro or 'ok',
                    status='erro' if erro else 'ok',
                )

        mapear(da_casa, list(por_casa))
        contagens = estado.contagens(ETAPA_AUTORIA, set(unicas))
    finally:
        arquivo.fechar()
        estado.fechar()

    ultimas = {linha['chave']: linha for linha in ler_csv(parcial, COLUNAS_AUTORIA_PARCIAL)}
    invalido = {
        'status_autoria': 'erro',
        'status_tramitacao': 'erro',
        'erro_autoria_tramitacao': 'link de matéria inválido',
    }
    for coluna in COLUNAS_AUTORIA:
        dados[coluna] = [
            ultimas.get(k, {}).get(coluna, '') if k else invalido.get(coluna, '') for k in chaves
        ]
    dados.to_csv(saida, index=False)
    return saida, contagens
