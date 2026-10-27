"""Montagem da tabela final do projeto a partir das matérias raspadas."""
import pandas as pd

from sapyl.estado import ler_csv
from sapyl.colunas import COLUNAS_FINAIS, COLUNAS_MATERIAS
from sapyl.materias import linha_vazia


def montar_final(arquivo_materias, links):
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
        linha = dict(ultimas.get(link['chave']) or {**linha_vazia(link), 'status': 'erro',
                                                     'erro': 'não raspada'})
        linha['Palavras'] = link['Palavras']
        linhas.append({c: linha.get(c, '') for c in COLUNAS_FINAIS})
    return pd.DataFrame(linhas, columns=COLUNAS_FINAIS)


def salvar_final(tabela, caminho):
    tabela.to_csv(caminho, index=False)


def ler_final(caminho):
    """Lê uma tabela final (nova ou de versões antigas, com coluna de índice)."""
    tabela = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    return tabela.drop(columns=[c for c in tabela.columns if c.startswith('Unnamed')])
