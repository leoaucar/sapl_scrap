import pandas as pd

def importar_palavras():
    df = pd.read_csv('./casas_legislativas.csv')
    palavras = df['palavras']

    return palavras

#tratamento e teste das palavras chave
#que tipo de testes usar nas palavras chave?