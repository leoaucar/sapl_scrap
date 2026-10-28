"""Montagem da tabela final do projeto a partir das matérias raspadas."""

from pathlib import Path

import pandas as pd

from sapyl.colunas import COLUNAS_FINAIS, COLUNAS_MATERIAS, Linha
from sapyl.estado import ler_csv
from sapyl.links import chave, normalizar_link
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


# --- Colunas da pessoa e filtro de relevantes (modo atualização) -------------

# Valores da coluna `Relevante` que marcam uma matéria (sem diferença de
# maiúsculas e espaços em volta)
COLUNA_RELEVANTE = 'Relevante'
VALORES_RELEVANTE = ('sim', 's', 'x', '1', 'true')


def colunas_extras(tabela: pd.DataFrame) -> list[str]:
    """Colunas que não são do programa (acrescentadas à mão: `Relevante`, anotações...)."""
    return [c for c in tabela.columns if c not in COLUNAS_FINAIS and not c.startswith('Unnamed')]


def eh_relevante(valor: object) -> bool:
    """Se o valor da coluna `Relevante` marca a matéria (veja VALORES_RELEVANTE)."""
    return str(valor).strip().lower() in VALORES_RELEVANTE


def filtrar_relevantes(tabela: pd.DataFrame) -> pd.DataFrame:
    """Só as linhas marcadas na coluna `Relevante`, na ordem original."""
    marcadas = tabela[COLUNA_RELEVANTE].map(eh_relevante)
    return tabela[marcadas].reset_index(drop=True)


def _chave_da_linha(casa: str, link_materia: str) -> str | None:
    normal = normalizar_link(casa, link_materia)
    return chave(casa, normal[1]) if normal else None


def juntar_colunas_extras(final: pd.DataFrame, entrada: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta ao `final` as colunas extras da `entrada`, casando as linhas pela chave.

    As colunas extras vão depois das do programa, na ordem em que estavam. Uma
    matéria repetida na entrada fica com os valores da primeira linha.
    """
    extras = colunas_extras(entrada)
    if not extras:
        return final
    valores: dict[str, dict[str, str]] = {}
    for _, linha in entrada.iterrows():
        k = _chave_da_linha(linha['Link Casa'], linha['Link Materia'])
        if k is not None and k not in valores:
            valores[k] = {c: linha[c] for c in extras}
    final = final.copy()
    chaves = [chave(c, i) for c, i in zip(final['Link Casa'], final['sapl_id'], strict=True)]
    for coluna in extras:
        final[coluna] = [valores.get(k, {}).get(coluna, '') for k in chaves]
    return final
