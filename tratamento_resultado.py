"""Limpeza da tabela de matérias raspadas para gerar o resultado final."""
import pandas as pd

# Nomes das colunas na ordem em que `raspador.py` grava os dados
NOMES_COLUNAS = {'0': 'IndiceOLD',
                 '1': 'Link Materia',
                 '2': 'Link Casa',
                 '3': 'Palavras',
                 '4': 'Titulo',
                 '5': 'Ementa',
                 '6': 'Ano',
                 '7': 'Data',
                 '8': 'Numero',
                 '9': 'Observacao',
                 '10': 'Assuntos',
                 '11': 'Tipo de Materia Legislativa',
                 '12': 'texto_original',
                 '13': 'texto_integral'}


def tratamento_resultados(tabela_resultados, atualizar):
    """Renomeia as colunas e remove os rótulos ("Ementa", "Ano"...) do texto raspado.

    Em projeto novo (`atualizar=False`), o link do texto original é relativo
    e recebe a URL da casa como prefixo; na atualização ele já é absoluto.
    """
    df = pd.read_csv(tabela_resultados, index_col=0, dtype=str)
    df = df.rename(columns=NOMES_COLUNAS)

    # Remove os rótulos que vêm junto com o texto de cada campo
    df['Ano'] = df['Ano'].str.replace('Ano\n\n', '')
    df['Ementa'] = df['Ementa'].str.replace('Ementa\n\n', '')
    df['Numero'] = df['Numero'].str.replace('Número\n\n', '')
    df['Observacao'] = df['Observacao'].str.replace('Observação', '')
    df['Observacao'] = df['Observacao'].str.replace('\n\n', '')
    df['Tipo de Materia Legislativa'] = df['Tipo de Materia Legislativa'].str.replace('Tipo de Matéria Legislativa\n\n', '')

    if atualizar == False:
        df['texto_original'] = df['Link Casa'] + df['texto_original'].str.replace('Texto Original\n\n', '')
    elif atualizar == True:
        df['texto_original'] = df['texto_original'].str.replace('Texto Original\n\n', '')

    df = df.replace(r'\r', ' ', regex=True)
    return df
