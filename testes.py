from raspador import raspar_materia_legislativa
from casas_legislativas import importar_casas, teste_url_ativa
import pandas as pd
from palavras_chave import importar_palavras
import requests
from bs4 import BeautifulSoup

def testar_raspagem_links():
    resultados = raspar_materia_legislativa("./teste_novo_proj/teste_novo_links_totais.csv")
    print(resultados[0])
    df = pd.DataFrame(resultados)
    df.to_csv('./arquivos_csv/teste_raspagem.csv')
    #columns=['Link Materia','Link Casa','titulo','ementa','ano','data','numero','observacao','assuntos']


def testar_palavras():
    palavras = importar_palavras()
    print('realizando a busca para termos:\n')
    for palavra in palavras:
        termos = palavra.split(",")
        for termo in termos:
            n = termos.index(termo)
            termo = termo.strip()
            termo = termo.replace(" ", "+")
            termo = "\""+termo+"\""
            termos[n] = termo
        termos = "+".join(termos)
        print(termos)

"""def teste_conteudo_atualizado():
    lista_casas = importar_casas()
    casas = teste_url_ativa(lista_casas[0:100])
    palavras = ['educacao','orcamento','saude']
    links_totais = []
    for casa in casas:
        if casa[1] == True:
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
    return casas"""

#def carregar_casas():
    #setup_casas(teste_curto)

escolha = input('Escolha teste:\nraspagem\npalavras\n')
if escolha == 'raspagem':
    testar_raspagem_links()
elif escolha == 'palavras':
    testar_palavras()
elif escolha == 'conteudo casas':
    testar_palavras()
#elif escolha = 'carregar casas':
#    carregar_casas()
'''
from raspador import raspar_resultados
import pandas as pd
nome_projeto = "teste_build1"
links_materias = raspar_resultados(nome_projeto+'_proj/'+nome_projeto+'_resultados_crus_casas'+'.csv')
df = pd.DataFrame(links_materias)

lista_removidos = []
def remove_irrelevantes(row):
    if row in lista_removidos:
        result = True
    else:
        result = False
    return result
df[df['0'].apply(remove_irrelevantes) == True]
df.apply(remove_irrelevantes)
'''