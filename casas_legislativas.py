import pandas as pd
import requests
from bs4 import BeautifulSoup

def importar_casas(estado=False):
    df = pd.read_excel('./arquivos_csv/casas_legislativas.xlsx')
    try:
        df = df[df['UF'].isin(estado)]
    except:
        pass
    if estado == True:
        lista_estados = ['RJ','SP','RS','SC','MG','ES','PR']
        df = df[df['UF'].isin(lista_estados)]
    casas = df['URL do serviço']
    #talvez aqui possamos usar os testes
    #garantir que só importaremos casas OK
    return casas

def teste_url_ativa(casas):
    resultado_casas = []
    for casa in casas:
        print(casa)
        try:
            response = requests.get(casa, timeout=5)
            if response.status_code == 200:
                resultado_casas.append((casa,True))
            else:
                resultado_casas.append((casa,False))
        except:
            continue
    return resultado_casas
#vou alterar essa função pra retornar um resultado rápido
#retornar também lista de casas OK (lista de bools)

def teste_conteudo_atualizado(casas, palavras):
    palavras = ['educacao','orcamento','saude']
    links_totais = []
    for casa in casas:
        for palavra in palavras:
            response = requests.get(casa + 'sistema/search/?q=' + palavra)
            soup = BeautifulSoup(response.text)
            for a in soup.find_all('a', href=True):
                links_totais.append([a['href'],palavra])
            #talvez usar um objeto de resultado
            if response.text > 5:
            #aqui vou alterar o content pra chamar o BS
                print('ok')
            #preciso de um segundo teste para verificar data
            else:
                print('não preenchido')
    return casas
#retornar função para retornar lista de casas ok

def setup_casas(nome_projeto, estado=False):
    try:
        casas_resultado = pd.read_csv('./'+nome_projeto+'_proj/'+'casas_resultado.csv')
        print('Última atualização continha ' + str(len(casas_resultado)) + ' casas com url ativas')
        casas_legislativas = 0
    except:
        casas_legislativas = 3

        ## Primeiro loop carrega a lista de casas legislativas
    while True:
        if casas_legislativas == 0:
            #casas_legislativas = input("Deseja atualizar status das casas legislativas? \nEscolha: 1 - sim 2 - não \n")
            casas_legislativas = 2
        else:
            break
        try:
            casas_legislativas = int(casas_legislativas)
            if casas_legislativas == 1 or casas_legislativas == 2:
                if casas_legislativas == 1:
                    print("Atualizando status das casas legislativas")
                    casas_resultado = teste_url_ativa(casas_resultado['0'])
                    print(casas_resultado)
                break
            else:
                print("Digite apenas o número 1 ou 2")
                continue
        except:
            print("Digite apenas o número 1 ou 2")
            continue

    if casas_legislativas == 3:
        print("Carregando Casas Legislativas")
        lista_casas = importar_casas(estado)
        casas_resultado = teste_url_ativa(lista_casas) #limitado 20 para teste
        print('realizando a busca em ' + str(len(casas_resultado)) + ' casas com url ativas')
        pd.DataFrame(casas_resultado).to_csv('./'+nome_projeto+'_proj/'+'/casas_resultado.csv', index=False)
        pd.DataFrame(casas_resultado).to_csv('./arquivos_csv/casas_resultado.csv',index=False)
    
    elif casas_legislativas == 2:
        casas_resultado['tupla'] = list(zip(casas_resultado['0'], casas_resultado['1']))
        casas_resultado = casas_resultado['tupla']

    return casas_resultado
#fazer testes de conteudo
