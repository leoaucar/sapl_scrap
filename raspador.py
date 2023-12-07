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
            links_totais.append(str(link)[:-1] + a['href'])
            
    links_materias = []
    for i in links_totais:
        pass
        #depois preciso de informações da casa nessa lista
    return links_totais
#aqui vou precisar raspar os resultados da busca página a página

def raspar_materia_legislativa(conteudo):
    resultado = conteudo
    return resultado
#aqui raspo o conteudo de cada matéria legislativa