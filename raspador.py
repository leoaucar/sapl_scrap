from bs4 import BeautifulSoup
import requests
import pandas as pd


def raspar_resultados(tabela):
    #loopa pelas paginas selecionadno os conteudos
    resultados = tabela['conteudo']
    for i in resultados:
        materia = raspar_materia_legislativa(i)
        #preciso exportar esses resultados atualizando a tabela
    return tabela
#aqui vou precisar raspar os resultados da busca página a página

def raspar_materia_legislativa(conteudo):
    resultado = conteudo
    return resultado
#aqui raspo o conteudo de cada matéria legislativa