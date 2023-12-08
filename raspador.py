from bs4 import BeautifulSoup
import pandas as pd
import re

def raspar_resultados(resultados_busca):
    #loopa pelas paginas selecionadno os conteudos
    links_totais = []
    resultados = pd.read_csv(resultados_busca, encoding='latin-1')
    for i in range(len(resultados)):
        html = resultados.loc[i,'html']
        link = resultados.loc[i,'Casa']
        palavra = resultados.loc[i,'Palavra']
        soup = BeautifulSoup(html)
        for a in soup.find_all('a', href=True):
            links_totais.append([str(link)[:-1] + a['href'],link,palavra])
            
    links_materias = []
    for link in links_totais:
        if ('materia' in link[0]) and (('pesquisar' not in link[0]) and ('media' not in link[0])): #considerar sessao e normas dps
            links_materias.append(link)
        #depois preciso de informações da casa nessa lista
        #preciso limpar duplicados
    return links_materias
#aqui vou precisar raspar os resultados da busca página a página

def raspar_materia_legislativa(conteudo):
    resultado = conteudo
    return resultado
#aqui raspo o conteudo de cada matéria legislativa