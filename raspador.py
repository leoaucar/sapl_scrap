from bs4 import BeautifulSoup
import pandas as pd

def raspar_resultados(resultados_busca):
    #loopa pelas paginas selecionadno os conteudos
    links_totais = []
    resultados = pd.read_csv(resultados_busca, encoding='latin-1')
    for i in range(len(resultados)):
        html = resultados.loc[i,'html']
        link = resultados.loc[i,'Casa']
        soup = BeautifulSoup(html)
        for a in soup.find_all('a', href=True):
            links_totais.append("Found the URL: " + str(link) + a['href'])
    
    links_materias = []
    for i in links_totais:
        pass
    
    return links_totais
#aqui vou precisar raspar os resultados da busca página a página

def raspar_materia_legislativa(conteudo):
    resultado = conteudo
    return resultado
#aqui raspo o conteudo de cada matéria legislativa

resultados = raspar_resultados('./arquivos_csv/resultado_busca2.csv')
print(resultados)