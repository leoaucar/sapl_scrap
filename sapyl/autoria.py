"""Acrescenta as colunas Autoria e Tramite a uma planilha de resultados.

Uso (de dentro da pasta com o CSV):
    python -m sapyl.autoria
O programa lista os CSVs da pasta e pergunta qual usar. O arquivo escolhido
não é alterado: o resultado vai para `<nome>_autoria_tramitacao.csv`.

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
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from bs4 import BeautifulSoup

from sapyl import registro
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import SEPARADOR, Linha
from sapyl.interface.entrada import Leitor, perguntar_opcao
from sapyl.links import no_endereco, normalizar_link
from sapyl.materias import Fontes
from sapyl.materias.api import Consultas
from sapyl.materias.valores import data_br, esquema_da_casa

BOAS_VINDAS = f'{registro.NOME}: autoria e tramitação\n'
SUFIXO_SAIDA = '_autoria_tramitacao'
log = registro.logger('autoria')


# Páginas de uma lista da API que seguimos, no máximo (cada uma tem até 100 itens)
MAX_PAGINAS_API = 20
# Colunas que esta etapa acrescenta
COLUNAS_AUTORIA = [
    'Autoria',
    'Tramite',
    'status_autoria',
    'status_tramitacao',
    'erro_autoria_tramitacao',
    'fonte_autoria',
]


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


def escolher_csv(pasta: str | Path, entrada: Leitor = input) -> Path | None:
    """Lista os CSVs da pasta (menos as saídas deste script) e pergunta qual usar."""
    arquivos = sorted(p for p in Path(pasta).glob('*.csv') if not p.stem.endswith(SUFIXO_SAIDA))
    if not arquivos:
        return None
    menu = ''.join(f'{i}- {p.name}\n' for i, p in enumerate(arquivos, start=1))
    escolha = perguntar_opcao(
        'Qual arquivo usar?\n' + menu, [str(i) for i in range(1, len(arquivos) + 1)], entrada
    )
    return arquivos[int(escolha) - 1]


def processar(caminho: str | Path, cliente: ClienteSAPL) -> Path:
    """Lê o CSV, busca autoria e tramitação de cada matéria e grava o novo arquivo."""
    dados = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    dados = dados.drop(columns=[c for c in dados.columns if c.startswith('Unnamed')])
    fontes = Fontes()
    linhas = []
    for i, link in enumerate(dados['Link Materia'], start=1):
        log.info('Autoria e tramitação %d de %d: %s', i, len(dados), link)
        linhas.append(raspar_autoria(link, cliente, fontes))
    for coluna in COLUNAS_AUTORIA:
        dados[coluna] = [linha[coluna] for linha in linhas]
    erros = dados['erro_autoria_tramitacao']
    saida = Path(caminho).with_name(Path(caminho).stem + SUFIXO_SAIDA + '.csv')
    dados.to_csv(saida, index=False)
    falhas = sum(1 for e in erros if e)
    log.info('Pronto: %s (%d matérias, %d com falha)', saida, len(dados), falhas)
    return saida


def main(
    pasta: str | Path = '.', entrada: Leitor = input, cliente: ClienteSAPL | None = None
) -> int:
    """Escolhe um CSV da pasta e grava a cópia com autoria e tramitação.

    Devolve o código de saída (0 ou 1).
    """
    registro.configurar(pasta, 'autoria_tramitacao', 'autoria')
    print(BOAS_VINDAS)
    try:
        caminho = escolher_csv(pasta, entrada)
    except (KeyboardInterrupt, EOFError):
        print('\nInterrompido.')
        return 1
    if caminho is None:
        print('Nenhum arquivo .csv nesta pasta. Copie para cá o resultado final de um projeto.')
        return 1
    try:
        # mesmo arquivo do programa principal quando roda na mesma pasta
        historico = Path(pasta) / '.sapl_historico.json'
        processar(caminho, cliente or ClienteSAPL(historico=str(historico)))
    except KeyboardInterrupt:
        print('\nInterrompido. O arquivo de entrada não foi alterado.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
