"""Leitura e formatação das palavras-chave de busca."""
import pandas as pd


def importar_palavras():
    """Lê a coluna `Palavras` de `arquivos_csv/palavras_chave.csv` ou, se não existir, do `.xlsx`."""
    try:
        df = pd.read_csv('./arquivos_csv/palavras_chave.csv', header=0)
    except:
        df = pd.read_excel('./arquivos_csv/palavras_chave.xlsx', header=0)
    palavras = df['Palavras']
    return palavras


def preparar_termos(palavras):
    """Converte cada linha de palavras-chave em uma consulta para a busca do SAPL.

    Termos separados por vírgula viram expressões exatas unidas por '+':
    "lingua portuguesa, norma culta" -> '"lingua+portuguesa"+"norma+culta"'
    """
    lista_termos = []
    for palavra in palavras:
        termos = palavra.split(",")
        for termo in termos:
            n = termos.index(termo)
            termo = termo.strip()
            termo = termo.replace(" ", "+")
            termo = "\""+termo+"\""
            termos[n] = termo
        termos = "+".join(termos)
        lista_termos.append(termos)
    return lista_termos
