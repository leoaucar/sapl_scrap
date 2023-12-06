from bs4 import BeautifulSoup
import pandas as pd

def raspar_resultados(tabela_busca,tabela_resultados):
    #loopa pelas paginas selecionadno os conteudos
    resultados = tabela_busca['conteudo']
    for i in resultados:
        materia = raspar_materia_legislativa(i)
        #preciso exportar esses resultados atualizando a tabela
    return tabela_resultados
#aqui vou precisar raspar os resultados da busca página a página

def raspar_materia_legislativa(conteudo):
    resultado = conteudo
    return resultado
#aqui raspo o conteudo de cada matéria legislativa