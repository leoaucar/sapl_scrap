"""Montagem da tabela final do projeto a partir das matérias raspadas."""

from pathlib import Path

import pandas as pd

from sapyl.colunas import COLUNAS_FINAIS, COLUNAS_MATERIAS, Linha
from sapyl.estado import ler_csv
from sapyl.materias import linha_vazia


def montar_final(arquivo_materias: str | Path, links: list[Linha]) -> pd.DataFrame:
    """Uma linha por matéria (na ordem de `links`), com a tentativa mais recente.

    `Palavras` vem da lista de links (todas as palavras que acharam a
    matéria). Uma matéria da lista que nunca foi raspada aparece com
    `status = erro`, nunca some em silêncio.
    """
    ultimas = {}
    for linha in ler_csv(arquivo_materias, COLUNAS_MATERIAS):
        ultimas[linha['chave']] = linha
    linhas = []
    for link in links:
        linha = dict(
            ultimas.get(link['chave'])
            or {**linha_vazia(link), 'status': 'erro', 'erro': 'não raspada'}
        )
        linha['Palavras'] = link['Palavras']
        linhas.append({c: linha.get(c, '') for c in COLUNAS_FINAIS})
    return pd.DataFrame(linhas, columns=COLUNAS_FINAIS)


def salvar_final(tabela: pd.DataFrame, caminho: str | Path) -> None:
    """Grava a tabela final, sem coluna de índice."""
    tabela.to_csv(caminho, index=False)


def ler_final(caminho: str | Path) -> pd.DataFrame:
    """Lê uma tabela final (nova ou de versões antigas, com coluna de índice)."""
    tabela = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    return tabela.drop(columns=[c for c in tabela.columns if c.startswith('Unnamed')])
