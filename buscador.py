import requests

#realizando a busca em casas legislativas
def buscar_resultados(casas_resultado, palavras):
    indice = 0
    urls_erro = []
    resultados = []
    for casa in casas_resultado: #limitado a 5 para teste
        if casa[1] == True:
            #print(casa[1])
            #aqui recupero os resultados de cada busca no sistema
            for palavra in palavras:
                pagina = 1
                while pagina < 10: #mantendo paginas limitadas a 10 para teste
                    url = casa[0] + 'sistema/search/?page=' + str(pagina) + '&q=' + palavra
                    print(url)
                    try:
                        response = requests.get(url)
                        urls_erro.append(url)
                    except:
                        continue
                    #soup = BeautifulSoup(response.text)
                    if response.status_code == 200:
                        #preciso separar paginas de resultados vazias das com resultados
                        resultados.append([indice, casa[0], palavra, pagina,response.text,url])
                        #print(soup.prettify())
                    else:
                        break
                    #print(response.status_code)
                    indice = indice + 1
                    pagina = pagina + 1
        else:
            continue
    return resultados


#necessario agora permitir que o buscador loope pelos resultados usando a funöäao de raspagem
#isso permitira montar a tabela de resultados
#os resultados sao os htmls das materias legistlativas
#em seguida vamos pegar e raspar as materias legislativas

#menu inicial e escolhas

#em novo projeto
#cria pasta do projeto
#carrega as palavras chave
#carrega as casas legislativas
#testa as casas legislativas
#raspa as casas legislativas

#em projeto ja executado
#atualiza as casas legislativas
#testa casas legislativas
#atualiza lista de palavras
#atualiza resultados