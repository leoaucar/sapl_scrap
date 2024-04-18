import requests

def setup_busca(casas_resultado):
    while True:
        limite_busca = input('Deseja limitar sua busca para teste? \n1- não(pesquisar todas as casas) \n2- 50 primeiras casas \n3- 50 últimas casas\n4- Apenas 10 casas\n')
        try:
            limite_busca = int(limite_busca)
            if limite_busca > 0 and limite_busca < 6:
                break
            else:
                print("Digite apenas o número 1, 2, 3 ou 4")
                continue
        except:
            print("Digite apenas o número 1, 2, 3 ou 4")
            continue

    if limite_busca == 1:
        casas_resultado = casas_resultado
    elif limite_busca == 2:
        casas_resultado = casas_resultado[:50]
    elif limite_busca == 3:
        len_casas = len(casas_resultado)
        casas_resultado = casas_resultado[len_casas-49:len_casas]
    elif limite_busca == 4:
        len_casas = len(casas_resultado)
        casas_resultado = casas_resultado[:10]
    return casas_resultado

#realizando a busca em casas legislativas
def buscar_resultados(casas_resultado, palavras):
    indice = 0
    urls_erro = []
    resultados = []
    numero_casa = 1
    for casa in casas_resultado:
        print("Busca na casa número: " + str(numero_casa) + " de " + str(len(casas_resultado)))
        numero_casa = numero_casa + 1
        if casa[1] == True:
            #print(casa[1])
            #aqui recupero os resultados de cada busca no sistema
            for palavra in palavras:
                pagina = 1
                while True: #altere para limitar paginas de teste
                    url = casa[0] + 'sistema/search/?page=' + str(pagina) + '&q=' + palavra
                    try:
                        response = requests.get(url)
                    except:
                        urls_erro.append(url)
                        continue
                    #soup = BeautifulSoup(response.text)
                    if response.status_code == 200:
                        print(url)
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
    print(urls_erro)
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