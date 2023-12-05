import pandas as pd

def montar_tabela(nome_csv):
    df = pd.DataFrame(columns=['Indice','Link','Titulo','html','palavras'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv')