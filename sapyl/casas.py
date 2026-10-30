"""Lista de casas legislativas: leitura, teste de quais estão no ar, filtros por estado e limite.

A tabela de casas (`casas_resultado.csv`) tem as colunas
`url, ativa, motivo, uf`. Tabelas antigas, com as colunas `0` (url) e `1`
(ativa), continuam sendo lidas; a UF vem da planilha de casas.
"""

import os
import zipfile
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from sapyl import registro
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import COLUNAS_CASAS
from sapyl.links import endereco_final, host
from sapyl.padroes import EntradaInvalida, Mapear, em_sequencia

# Estados usados quando a busca é restrita a Sul e Sudeste
ESTADOS_SUL_SUDESTE = ['RJ', 'SP', 'RS', 'SC', 'MG', 'ES', 'PR']

# Valores de `limite` no config.json: todas as casas, ou um teste com 10.
# '2' (50 primeiras) e '3' (50 últimas) só existem em projetos antigos.
LIMITE_TODAS = '1'
LIMITE_TESTE = '4'
CASAS_NO_TESTE = 10

COLUNAS_PLANILHA = ('UF', 'URL do serviço')

log = registro.logger('casas')


def _com_barra(url: object) -> str:
    url = str(url).strip()
    return url if url.endswith('/') else url + '/'


def importar_casas(planilha: str | Path) -> pd.DataFrame:
    """Lê a planilha de casas e devolve um DataFrame com `url` e `uf`.

    Planilha ausente, ilegível ou sem as colunas `UF` e `URL do serviço` vira
    `EntradaInvalida`, com a mensagem para a pessoa.
    """
    planilha = Path(planilha)
    if not planilha.is_file():
        raise EntradaInvalida(
            f'Não encontrei a planilha de casas legislativas {planilha.resolve()}. '
            'Rode o sapyl na pasta que tem a pasta arquivos_csv/ (a do repositório traz '
            'a planilha casas_legislativas.xlsx).'
        )
    try:
        df = pd.read_excel(planilha)
    except (OSError, ValueError, zipfile.BadZipFile) as erro:
        raise EntradaInvalida(f'Não consegui ler a planilha {planilha}: {erro}') from erro
    faltam = [c for c in COLUNAS_PLANILHA if c not in df.columns]
    if faltam:
        raise EntradaInvalida(
            f'A planilha {planilha} não tem a(s) coluna(s) {", ".join(faltam)}; '
            'o programa usa as colunas UF e URL do serviço.'
        )
    df = df[df['URL do serviço'].notna()]
    return pd.DataFrame(
        {
            'url': [_com_barra(u) for u in df['URL do serviço']],
            'uf': [str(u).strip().upper() for u in df['UF']],
        }
    ).reset_index(drop=True)


def testar_casa(url: str, cliente: ClienteSAPL) -> tuple[bool, str, str]:
    """(no ar, motivo, url_final) de uma casa: uma requisição à página inicial."""
    resposta = cliente.get(url, timeout=(5, 5), max_tentativas=2, avisar=False)
    resposta.fechar()
    final = ''
    if resposta.ok and resposta.bruta is not None:
        final = endereco_final(getattr(resposta.bruta, 'url', ''), url)
    if final:
        log.info('%s redireciona para %s', url, final)
    return resposta.ok, resposta.erro, final


def testar_casas(
    casas: pd.DataFrame, cliente: ClienteSAPL, mapear: Mapear = em_sequencia
) -> pd.DataFrame:
    """Testa se o site de cada casa responde. Nenhuma casa sai da lista.

    Devolve COLUNAS_CASAS, na ordem da tabela; `motivo` explica por que a casa
    está inativa (`HTTP 500`, `timeout`...), e `url_final` guarda o endereço
    novo quando o site redireciona para outro domínio. `mapear` diz como rodar
    os testes (padrão: uma casa por vez; o programa testa várias ao mesmo tempo).
    """
    urls = list(casas['url'])
    posicao = {}
    for i, url in enumerate(urls, start=1):
        posicao.setdefault(url, i)

    def testar(url: str) -> tuple[bool, str, str]:
        registro.andamento(
            log,
            registro.TESTE,
            posicao[url],
            len(urls),
            'Testando casa %d de %d: %s',
            posicao[url],
            len(urls),
            url,
        )
        return testar_casa(url, cliente)

    resultados = mapear(testar, urls)
    linhas = [
        {'url': url, 'ativa': ok, 'motivo': motivo, 'uf': uf, 'url_final': final}
        for url, uf, (ok, motivo, final) in zip(urls, casas['uf'], resultados, strict=True)
    ]
    return pd.DataFrame(linhas, columns=COLUNAS_CASAS)


def _para_bool(valor: object) -> bool:
    return str(valor).strip().lower() in ('true', '1', 'sim', 's')


def ler_tabela_casas(caminho: str | Path, planilha: str | Path | None = None) -> pd.DataFrame:
    """Lê `casas_resultado.csv` (formato novo ou antigo) com as colunas de COLUNAS_CASAS.

    Se a tabela não tiver UF, ela é buscada na `planilha` de casas pela URL.
    """
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    if 'url' not in df.columns and '0' in df.columns:
        df = df.rename(columns={'0': 'url', '1': 'ativa'})
    df['url'] = [_com_barra(u) for u in df['url']]
    df['ativa'] = [_para_bool(v) for v in df['ativa']]
    if 'motivo' not in df.columns:
        df['motivo'] = ''
    if 'url_final' not in df.columns:
        df['url_final'] = ''
    if 'uf' not in df.columns or (df['uf'] == '').any():
        ufs = {}
        if planilha is not None and os.path.exists(planilha):
            ufs = dict(importar_casas(planilha)[['url', 'uf']].values)
        atual = df['uf'] if 'uf' in df.columns else pd.Series([''] * len(df))
        df['uf'] = [u if u else ufs.get(url, '') for u, url in zip(atual, df['url'], strict=True)]
    return df[COLUNAS_CASAS].reset_index(drop=True)


def enderecos_finais(casas: pd.DataFrame) -> dict[str, str]:
    """{host original: url_final} das casas que redirecionam."""
    if 'url_final' not in casas.columns:
        return {}
    return {host(u): f for u, f in zip(casas['url'], casas['url_final'], strict=True) if f}


def salvar_tabela_casas(casas: pd.DataFrame, caminho: str | Path) -> None:
    """Grava a tabela de casas (COLUNAS_CASAS), substituindo o arquivo."""
    casas.reindex(columns=COLUNAS_CASAS, fill_value='').to_csv(caminho, index=False)


def ufs(casas: pd.DataFrame) -> list[str]:
    """As UFs da tabela, em ordem alfabética, sem repetir nem vazias."""
    return sorted({str(u) for u in casas['uf'] if str(u).strip()})


def filtrar_estados(casas: pd.DataFrame, estados: Iterable[str]) -> pd.DataFrame:
    """Só as casas dos `estados` (siglas); lista vazia = todas."""
    estados = {e.strip().upper() for e in estados}
    if not estados:
        return casas.reset_index(drop=True)
    return casas[casas['uf'].isin(estados)].reset_index(drop=True)


def limitar_casas(casas: pd.DataFrame, opcao: str) -> pd.DataFrame:
    """Aplica `limite` do config.json: '1' todas, '4' as 10 primeiras (teste);
    '2' e '3' (50 primeiras, 50 últimas) só em projetos antigos."""
    opcao = str(opcao)
    if opcao == '2':
        casas = casas[:50]
    elif opcao == '3':
        casas = casas[-50:]
    elif opcao == LIMITE_TESTE:
        casas = casas[:CASAS_NO_TESTE]
    elif opcao != '1':
        raise ValueError(f'Opção de limite inválida: {opcao}')
    return casas.reset_index(drop=True)
