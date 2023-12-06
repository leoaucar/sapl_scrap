import pandas as pd

def montar_tabela_busca(nome_csv):
    df = pd.DataFrame(columns=['Indice','Casa','Palavra','Página','html'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv')

def montar_tabela_resultados():
    pass