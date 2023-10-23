import pandas as pd
import requests

def importar_casas():
    df = pd.read_csv('./casas_legislativas.csv')
    casas = df['casas']
    #talvez aqui possamos usar os testes
    #garantir que só importaremos casas OK
    return casas

def teste_url_ativa(casas):
    for casa in casas:
        response = requests.get(casa)
        if response.status_code == 200:
            print('ok')
        else:
            print('não ok')
    return casas
#vou alterar essa função pra retornar um resultado rápido
#retornar também lista de casas OK (lista de bools)

testes = ['genero','ideologia','orçamento']
def teste_conteudo_atualizado(casas):
    for casa in casas:
        for palavra in testes:
            response = requests.get(casa + 'sistema/search/?q=' + palavra)
            #talvez usar um objeto de resultado
            if response.text > 5:
            #aqui vou alterar o content pra chamar o BS
                print('ok')
            #preciso de um segundo teste para verificar data
            else:
                print('não preenchido')
    return casas
#retornar função para retornar lista de casas ok