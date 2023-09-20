import pandas as pd

def importar_casas():
    df = pd.read_csv('./casas_legislativas.csv')
    casas = df['casas']

    return casas