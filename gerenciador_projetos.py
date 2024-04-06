import pandas as pd
import os
import shutil
from datetime import datetime

def criacao_projeto(nova_tabela, nome_padrao=True, nome_antigo=None):
    if nome_padrao == True:
        #nome = nome_antigo + "_atualizacao_" + str(datetime.today())
        nome = input('Defina o nome do projeto\n')
    else:
        nome = input('Defina o nome do projeto\n')
    os.mkdir('./'+nome+'_proj/')
    if nova_tabela == False:
        shutil.copyfile('./arquivos_csv/casas_resultado.csv', './'+nome+'_proj/'+'casas_resultado'+'.csv')
    montar_tabela_busca(nome,nome+'_resultados_crus_casas')
    #montar_tabela_links(nome+'_links_totais')
    #montar_tabela_conteudos(nome+'_materias_legislativas')
    return nome

def montar_tabela_busca(nome_projeto,nome_tabela):
    df = pd.DataFrame(columns=['Indice','Casa','Palavra','Pagina','html','link'])
    df.to_csv('./'+nome_projeto+'_proj/'+nome_tabela+'.csv', index=False)

def montar_tabela_links(nome_csv):
    df = pd.DataFrame(columns=['Indice','Casa','Palavra','link_materia'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv', index=False)

def montar_tabela_conteudos(nome_csv):
    df = pd.DataFrame(columns=['Indice','Casa','Palavra','link_materia','Titulo','Ementa'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv', index=False)