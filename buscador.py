import requests
from palavras_chave import importar_palavras
from casas_legislativas import importar_casas, teste_url_ativa
from raspador import raspar_resultados
from gerenciador_projetos import montar_tabela
from bs4 import BeautifulSoup

lista_casas = importar_casas()
#print(lista_casas)

#validacao das casas legislativas online
casas_resultado = teste_url_ativa(lista_casas[0:20]) #limitado 20 para teste
#print(casas_resultado)

#validacao das palavras chave
palavras = importar_palavras()
#print(palavras)

montar_tabela('projeto')

#realizando a busca em casas legislativas
for casa in casas_resultado: #limitado a 5 para teste
    indice = 0
    if casa[1] == True:
        #print(casa[1])
        #aqui recupero os resultados de cada busca no sistema
        for i in palavras:
            pagina = 1
            while pagina < 10: #mantendo paginas limitadas a 10 para teste
                url = casa[0] + 'sistema/search/?page=' + str(pagina) + '&q=' + i
                print(url)
                response = requests.get(url)
                soup = BeautifulSoup(response.text)
                if response.status_code == 200:
                    print('ok')
                    #print(soup.prettify())
                else:
                    break
                #print(response.status_code)
                indice = indice + 1
                pagina = pagina + 1
    else:
        continue
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