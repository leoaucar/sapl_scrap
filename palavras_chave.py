import pandas as pd

def importar_palavras():
    df = pd.read_csv('./casas_legislativas.csv')
    palavras = df['palavras']

    return palavras