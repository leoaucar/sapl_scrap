import pandas as pd

def criacao_projeto():
    nome = input('Defina o nome do projeto')
    montar_tabela_busca(nome+'_busca_casas_legislativas')
    #montar_tabela_links(nome+'_links_totais')
    #montar_tabela_conteudos(nome+'_materias_legislativas')
    return nome

def montar_tabela_busca(nome_csv):
    df = pd.DataFrame(columns=['Indice','Casa','Palavra','Pagina','html','link'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv', index=False)

def montar_tabela_links(nome_csv):
    df = pd.DataFrame(columns=['Indice','Casa','Palavra','link_materia'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv', index=False)

def montar_tabela_conteudos(nome_csv):
    df = pd.DataFrame(columns=['Indice','Casa','Palavra','link_materia','Titulo','Ementa'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv', index=False)