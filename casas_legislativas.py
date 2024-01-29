import pandas as pd
import requests
from bs4 import BeautifulSoup

def importar_casas():
    df = pd.read_excel('./arquivos_csv/casas_legislativas.xlsx')
    casas = df['URL do serviço']
    #talvez aqui possamos usar os testes
    #garantir que só importaremos casas OK
    return casas

def teste_url_ativa(casas):
    resultado_casas = []
    for casa in casas:
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

#fazer testes de conteudo
