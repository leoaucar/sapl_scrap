from bs4 import BeautifulSoup
import pandas as pd
import requests

def raspar_resultados(resultados_busca):
    #loopa pelas paginas selecionadno os conteudos
    links_totais = []
    resultados = pd.read_csv(resultados_busca, encoding='UTF-8')
    for i in range(len(resultados)):
        html = resultados.loc[i,'html']
        link = resultados.loc[i,'Casa']
        palavra = resultados.loc[i,'Palavra']
        soup = BeautifulSoup(html)
        for a in soup.find_all('a', href=True):
            links_totais.append([str(link)[:-1] + a['href'],link,palavra])
            
    links_materias = []
    for link in links_totais:
        if ('materia' in link[0]) and (('pesquisar' not in link[0]) and ('media' not in link[0]) and ('documentoacessorio' not in link[0])): #considerar sessao e normas dps
            links_materias.append(link)
        #depois preciso de informações da casa nessa lista
        #preciso limpar duplicados
    return links_materias
#aqui vou precisar raspar os resultados da busca página a página

def raspar_materia_legislativa(conteudo):
    links_achados = pd.read_csv(conteudo)
    resultados=[]
    indice = 0
    for i in links_achados.iloc[:,1]:#limitado a 50 para teste
        response = requests.get(i)
        dados_atuais = list(links_achados.iloc[indice,:])
        soup = BeautifulSoup(response.text)
        
        #raspa titulo
        for titulo in soup.find_all('h1', {"class": "page-header"}):
            titulo = titulo.text
            dados_atuais.append(titulo.strip())
            print(titulo.strip())

        for ementa in soup.find_all('div', {"id": "div_id_ementa"}):
            ementa = ementa.text
            dados_atuais.append(ementa.strip())
            print(ementa.strip())
        resultados.append(dados_atuais)
        indice = indice + 1
    return resultados
        
#aqui raspo o conteudo de cada matéria legislativa