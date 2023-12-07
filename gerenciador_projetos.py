import pandas as pd

def montar_tabela_busca(nome_csv):
    df = pd.DataFrame(columns=['Indice','Casa','Palavra','Pagina','html','link'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv', index=False)

def montar_tabela_resultados():
    pass