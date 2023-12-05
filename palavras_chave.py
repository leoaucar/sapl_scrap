import pandas as pd

def importar_palavras():
    df = pd.read_csv('./arquivos_csv/palavras_chave.csv', header=0)
    palavras = df['Palavras']

    return palavras

#tratamento e teste das palavras chave
#que tipo de testes usar nas palavras chave?