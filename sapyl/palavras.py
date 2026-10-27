"""Leitura e formatação das palavras-chave de busca."""
import os

import pandas as pd


def importar_palavras(pasta='arquivos_csv'):
    """Lê a coluna `Palavras` de `<pasta>/palavras_chave.csv` ou, se não existir, do `.xlsx`."""
    csv = os.path.join(pasta, 'palavras_chave.csv')
    if os.path.exists(csv):
        df = pd.read_csv(csv, header=0)
    else:
        df = pd.read_excel(os.path.join(pasta, 'palavras_chave.xlsx'), header=0)
    return [str(p) for p in df['Palavras'].dropna() if str(p).strip()]


def preparar_termos(palavras):
    """Converte cada linha de palavras-chave em uma consulta para a busca do SAPL.

    Termos separados por vírgula viram expressões exatas unidas por '+':
    "lingua portuguesa, norma culta" -> '"lingua+portuguesa"+"norma+culta"'
    """
    consultas = []
    for linha in palavras:
        termos = [t.strip() for t in str(linha).split(',') if t.strip()]
        consultas.append('+'.join('"' + '+'.join(t.split()) + '"' for t in termos))
    return consultas
