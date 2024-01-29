from palavras_chave import importar_palavras, preparar_termos
from casas_legislativas import importar_casas, teste_url_ativa
from raspador import raspar_resultados, raspar_materia_legislativa
from gerenciador_projetos import criacao_projeto
from buscador import buscar_resultados
import pandas as pd
import csv

try:
    casas_resultado = pd.read_csv('./arquivos_csv/casas_resultado.csv')
    print('Última atualização continha ' + str(len(casas_resultado)) + ' casas com url ativas')
    casas_legislativas = 0
except:
    print("Carregando casas Legislativas")
    casas_legislativas = 1

## Primeiro loop carrega a lista de casas legislativas
while True:
    if casas_legislativas != 1:
        casas_legislativas = input("Deseja atualizar a lista de casas legislativas? \nEscolha: 1 - sim 2 - não  ")
    try:
        casas_legislativas = int(casas_legislativas)
        if casas_legislativas == 1 or casas_legislativas == 2:
            break
        else:
            print("Digite apenas o número 1 ou 2")
            continue
    except:
        print("Digite apenas o número 1 ou 2")
        continue

if casas_legislativas == 1:
    print("carregando casas legislativas")
    lista_casas = importar_casas()
    casas_resultado = teste_url_ativa(lista_casas) #limitado 20 para teste
    print('realizando a busca em ' + str(len(casas_resultado)) + ' casas com url ativas')
    pd.DataFrame(casas_resultado).to_csv('./arquivos_csv/casas_resultado.csv')



#validacao das palavras chave
palavras = importar_palavras()
palavras = preparar_termos(palavras)
print('realizando a busca para termos:\n')
for i in palavras:
    print(i)

#criação do projeto
nome_projeto = criacao_projeto()

#busca de resultados
while True:
    limite_busca = input('Deseja limitar sua busca para teste? \n1- não(pesquisar todas as casas) \n2- 50 primeiras casas \n3- 50 últimas casas')
    try:
        limite_busca = int(limite_busca)
        if limite_busca > 0 and limite_busca < 4:
            break
        else:
            print("Digite apenas o número 1, 2 ou 3")
            continue
    except:
        print("Digite apenas o número 1, 2 ou 3")
        continue

if limite_busca == 1:
    casas_resultado = casas_resultado
elif limite_busca == 2:
    casas_resultado = casas_resultado[:50]
elif limite_busca == 3:
    len_casas = len(casas_resultado)
    casas_resultado = casas_resultado[len_casas-51:len_casas]

resultados = buscar_resultados(casas_resultado, palavras)
with open('arquivos_csv/'+nome_projeto+'_busca_casas_legislativas'+'.csv', 'a', encoding="UTF-8") as file:
    writer = csv.writer(file)
    for i in resultados:
        writer.writerow(i)


#aqui trazemos os links da planilha de resultados da busca para a plailha de links achados
#montar_tabela_links('links_achados')
resultados = raspar_resultados('./arquivos_csv/'+nome_projeto+'_busca_casas_legislativas'+'.csv')
df = pd.DataFrame(resultados)
df.to_csv("arquivos_csv/"+nome_projeto+"_links_totais"+".csv")

#aqui trazemos os dados da planilha de links para a planilha de materias legislativas
#montar_tabela_conteudos('conteudos_materias')
resultados = raspar_materia_legislativa("arquivos_csv/"+nome_projeto+"_links_totais"+".csv")

print(resultados[0:1])
df = pd.DataFrame(resultados)
df.to_csv("./arquivos_csv/"+nome_projeto+"_materias_legislativas"+".csv")
#columns=['Link Materia','Link Casa','titulo','ementa','ano','data','numero','observacao','assuntos']