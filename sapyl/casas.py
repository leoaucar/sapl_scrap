"""Lista de casas legislativas: leitura, teste de quais estão no ar, filtros.

A tabela de casas (`casas_resultado.csv`) tem as colunas
`url, ativa, motivo, uf`. Tabelas antigas, com as colunas `0` (url) e `1`
(ativa), continuam sendo lidas; a UF vem da planilha de casas.
"""

import os
from pathlib import Path

import pandas as pd

from sapyl import registro
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import COLUNAS_CASAS
from sapyl.links import endereco_final, host
from sapyl.padroes import Mapear, em_sequencia

# Estados usados quando a busca é restrita a Sul e Sudeste
ESTADOS_SUL_SUDESTE = ['RJ', 'SP', 'RS', 'SC', 'MG', 'ES', 'PR']

# Opções do menu de limite de casas (para testes)
OPCOES_LIMITE = {
    '1': 'todas as casas',
    '2': '50 primeiras casas',
    '3': '50 últimas casas',
    '4': 'apenas 10 casas',
}
PERGUNTA_LIMITE = 'Deseja limitar sua busca para teste?\n' + ''.join(
    f'{k}- {v}\n' for k, v in OPCOES_LIMITE.items()
)

log = registro.logger('casas')


def _com_barra(url: object) -> str:
    url = str(url).strip()
    return url if url.endswith('/') else url + '/'


def importar_casas(planilha: str | Path) -> pd.DataFrame:
    """Lê a planilha de casas e devolve um DataFrame com `url` e `uf`."""
    df = pd.read_excel(planilha)
    df = df[df['URL do serviço'].notna()]
    return pd.DataFrame(
        {
            'url': [_com_barra(u) for u in df['URL do serviço']],
            'uf': [str(u).strip().upper() for u in df['UF']],
        }
    ).reset_index(drop=True)


def testar_casa(url: str, cliente: ClienteSAPL) -> tuple[bool, str, str]:
    """(no ar, motivo, url_final) de uma casa: uma requisição à página inicial."""
    resposta = cliente.get(url, timeout=(5, 5), max_tentativas=2)
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
        log.info('Testando casa %d de %d: %s', posicao[url], len(urls), url)
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


def filtrar_sul_sudeste(casas: pd.DataFrame) -> pd.DataFrame:
    """Só as casas dos estados de ESTADOS_SUL_SUDESTE."""
    return casas[casas['uf'].isin(ESTADOS_SUL_SUDESTE)].reset_index(drop=True)


def limitar_casas(casas: pd.DataFrame, opcao: str) -> pd.DataFrame:
    """Aplica a opção do menu de limite (veja OPCOES_LIMITE)."""
    opcao = str(opcao)
    if opcao == '2':
        casas = casas[:50]
    elif opcao == '3':
        casas = casas[-50:]
    elif opcao == '4':
        casas = casas[:10]
    elif opcao != '1':
        raise ValueError(f'Opção de limite inválida: {opcao}')
    return casas.reset_index(drop=True)
