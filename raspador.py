from bs4 import BeautifulSoup
import pandas as pd

def raspar_resultados(resultados_busca):
    #loopa pelas paginas selecionadno os conteudos
    resultados = pd.read_csv(resultados_busca, encoding='latin-1')
    for i in range(len(resultados)):
        html = resultados.loc[i,'html']
        #link = resultados.loc[i:'link']
        soup = BeautifulSoup(html)
        for a in soup.find_all('a', href=True):
            print("Found the URL: " + a['href'])
            pass
    #return tabela_materias
#aqui vou precisar raspar os resultados da busca página a página

def raspar_materia_legislativa(conteudo):
    resultado = conteudo
    return resultado
#aqui raspo o conteudo de cada matéria legislativa

raspar_resultados('./arquivos_csv/resultado_busca2.csv')
