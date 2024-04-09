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
        i = i.replace('/ta','')
        response = requests.get(i)
        dados_atuais = list(links_achados.iloc[indice,:])
        soup = BeautifulSoup(response.text)
        
        #raspa titulo
        titulo = ''
        for titulo in soup.find_all('h1', {"class": "page-header"}):
            titulo = titulo.text
        dados_atuais.append(titulo.strip())

        ementa = ''
        for ementa in soup.find_all('div', {"id": "div_id_ementa"}):
            ementa = ementa.text
        dados_atuais.append(ementa.strip())

        ano = ''
        for ano in soup.find_all('div', {"id": "div_id_ano"}):
            ano = ano.text
        dados_atuais.append(ano.strip())
        
        data = ''
        for data in soup.find_all('div', {"id": "div_id_data"}):
            data = data.text
        dados_atuais.append(data.strip())
        
        numero = ''
        for numero in soup.find_all('div', {"id": "div_id_numero"}):
            numero = numero.text
        dados_atuais.append(numero.strip())
        
        observacao = ''
        for observacao in soup.find_all('div', {"id": "div_id_observacao"}):
            observacao = observacao.text
        dados_atuais.append(observacao.strip())
        
        assuntos = ''
        for assuntos in soup.find_all('div', {"id": "div_id_assuntos"}):
            assuntos = assuntos.text
        dados_atuais.append(assuntos.strip())

        tipo_materia = ''
        for tipo_materia in soup.find_all('div', {"id": "div_id_tipo"}):
            tipo_materia = tipo_materia.text
        dados_atuais.append(tipo_materia.strip())

        #texto_original = ''
        #for texto_original in soup.find_all('div', {"id": "div_id_texto_original"}):
        #    texto_original = texto_original.text
        #    for a in texto_original.find_all('a', href=True):
        #        texto_original = a['href']
        #dados_atuais.append(texto_original.strip())

        #texto_integral = ''
        #for texto_integral in soup.find_all('div', {"id": "div_id_texto_integral"}):
        #    texto_original = texto_integral.text
        #    for a in texto_integral.find_all('a', href=True):
        #        texto_integral = a['href']
        #dados_atuais.append(texto_integral.strip())

        #materia = ''
        #for materia in soup.find_all('div', {"id": "div_id_materia"}):
        #    materia = materia.text
        #    for a in materia.find_all('a', href=True):
        #        materia = a['href']
        #dados_atuais.append(materia.strip())

        resultados.append(dados_atuais)
        print(dados_atuais)
        indice = indice + 1
    return resultados

def atualizar_materia_legislativa(conteudo):
    links_achados = pd.read_csv(conteudo, index_col=0)
    resultados=[]
    indice = 0
    for i in links_achados.iloc[:,1]:#limitado a 50 para teste
        i = i.replace('/ta','')
        response = requests.get(i)
        dados_atuais = list(links_achados.iloc[indice,:])
        soup = BeautifulSoup(response.text)
        
        #raspa titulo
        titulo = ''
        for titulo in soup.find_all('h1', {"class": "page-header"}):
            titulo = titulo.text
        dados_atuais.append(titulo.strip())

        ementa = ''
        for ementa in soup.find_all('div', {"id": "div_id_ementa"}):
            ementa = ementa.text
        dados_atuais.append(ementa.strip())

        ano = ''
        for ano in soup.find_all('div', {"id": "div_id_ano"}):
            ano = ano.text
        dados_atuais.append(ano.strip())
        
        data = ''
        for data in soup.find_all('div', {"id": "div_id_data"}):
            data = data.text
        dados_atuais.append(data.strip())
        
        numero = ''
        for numero in soup.find_all('div', {"id": "div_id_numero"}):
            numero = numero.text
        dados_atuais.append(numero.strip())
        
        observacao = ''
        for observacao in soup.find_all('div', {"id": "div_id_observacao"}):
            observacao = observacao.text
        dados_atuais.append(observacao.strip())
        
        assuntos = ''
        for assuntos in soup.find_all('div', {"id": "div_id_assuntos"}):
            assuntos = assuntos.text
        dados_atuais.append(assuntos.strip())

        tipo_materia = ''
        for tipo_materia in soup.find_all('div', {"id": "div_id_tipo"}):
            tipo_materia = tipo_materia.text
        dados_atuais.append(tipo_materia.strip())

        #texto_original = ''
        #for texto_original in soup.find_all('div', {"id": "div_id_texto_original"}):
        #    texto_original = texto_original.text
        #    for a in texto_original.find_all('a', href=True):
        #        texto_original = a['href']
        #dados_atuais.append(texto_original.strip())

        #texto_integral = ''
        #for texto_integral in soup.find_all('div', {"id": "div_id_texto_integral"}):
        #    texto_original = texto_integral.text
        #    for a in texto_integral.find_all('a', href=True):
        #        texto_integral = a['href']
        #dados_atuais.append(texto_integral.strip())

        #materia = ''
        #for materia in soup.find_all('div', {"id": "div_id_materia"}):
        #    materia = materia.text
        #    for a in materia.find_all('a', href=True):
        #        materia = a['href']
        #dados_atuais.append(materia.strip())

        resultados.append(dados_atuais)
        print(dados_atuais)
        indice = indice + 1
    return resultados