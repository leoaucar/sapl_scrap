"""Lista de casas legislativas: leitura, teste de quais estão no ar, filtros.

A tabela de casas (`casas_resultado.csv`) tem as colunas
`url, ativa, motivo, uf`. Tabelas antigas, com as colunas `0` (url) e `1`
(ativa), continuam sendo lidas; a UF vem da planilha de casas.
"""
import os

import pandas as pd

import registro

# Estados usados quando a busca é restrita a Sul e Sudeste
ESTADOS_SUL_SUDESTE = ['RJ', 'SP', 'RS', 'SC', 'MG', 'ES', 'PR']
COLUNAS_CASAS = ['url', 'ativa', 'motivo', 'uf']

# Opções do menu de limite de casas (para testes)
OPCOES_LIMITE = {
    '1': 'todas as casas',
    '2': '50 primeiras casas',
    '3': '50 últimas casas',
    '4': 'apenas 10 casas',
}
PERGUNTA_LIMITE = ('Deseja limitar sua busca para teste?\n'
                   + ''.join(f'{k}- {v}\n' for k, v in OPCOES_LIMITE.items()))

log = registro.logger('casas')


def _com_barra(url):
    url = str(url).strip()
    return url if url.endswith('/') else url + '/'


def importar_casas(planilha):
    """Lê a planilha de casas e devolve um DataFrame com `url` e `uf`."""
    df = pd.read_excel(planilha)
    df = df[df['URL do serviço'].notna()]
    return pd.DataFrame({
        'url': [_com_barra(u) for u in df['URL do serviço']],
        'uf': [str(u).strip().upper() for u in df['UF']],
    }).reset_index(drop=True)


def testar_casas(casas, cliente):
    """Testa se o site de cada casa responde. Nenhuma casa sai da lista.

    Devolve as colunas `url, ativa, motivo, uf`; `motivo` explica por que a
    casa está inativa (`HTTP 500`, `timeout`...).
    """
    linhas = []
    for i, casa in enumerate(casas.itertuples(index=False), start=1):
        log.info('Testando casa %d de %d: %s', i, len(casas), casa.url)
        resposta = cliente.get(casa.url, timeout=(5, 5), max_tentativas=2)
        resposta.fechar()
        linhas.append({'url': casa.url, 'ativa': resposta.ok,
                       'motivo': resposta.erro, 'uf': casa.uf})
    return pd.DataFrame(linhas, columns=COLUNAS_CASAS)


def _para_bool(valor):
    return str(valor).strip().lower() in ('true', '1', 'sim', 's')


def ler_tabela_casas(caminho, planilha=None):
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
    if 'uf' not in df.columns or (df['uf'] == '').any():
        ufs = {}
        if planilha is not None and os.path.exists(planilha):
            ufs = dict(importar_casas(planilha)[['url', 'uf']].values)
        atual = df['uf'] if 'uf' in df.columns else pd.Series([''] * len(df))
        df['uf'] = [u if u else ufs.get(url, '') for u, url in zip(atual, df['url'])]
    return df[COLUNAS_CASAS].reset_index(drop=True)


def salvar_tabela_casas(casas, caminho):
    casas[COLUNAS_CASAS].to_csv(caminho, index=False)


def filtrar_sul_sudeste(casas):
    return casas[casas['uf'].isin(ESTADOS_SUL_SUDESTE)].reset_index(drop=True)


def limitar_casas(casas, opcao):
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
