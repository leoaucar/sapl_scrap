from palavras_chave import importar_palavras, preparar_termos
from casas_legislativas import setup_casas
from raspador import raspar_resultados, raspar_materia_legislativa, atualizar_materia_legislativa
from gerenciador_projetos import criacao_projeto
from buscador import buscar_resultados, setup_busca
from tratamento_resultado import tratamento_resultados
import pandas as pd
import csv
import os
from datetime import datetime

### Primeira parte do código da conta da criação do projeto
## Verifica se existem projeto (dummy por enquanto) e dps se usuário deseja criar novo
#print("Projetos encontrados:")
#for filename in os.listdir():
#    if filename.endswith('_proj'):
#        print(filename)
#criar_projeto = input("Deseja criar um novo projeto? \n1- sim, 2- não")

#criação do projeto
#a criacao_projeto() capta nome desejado do projeto e tb chama a "montar tabela busca"
while True:
    nova_tabela = input("Deseja usar a mesma tabela de casas do último projeto? 1- sim, 2- não\n")
    if nova_tabela == '1':
        nova_tabela = False
        break
    elif nova_tabela == '2':
        nova_tabela = True
        break
    else:
        print("Digite apenas o numero 1 ou 2")
        continue

while True:
    atualizar = input("Deseja apenas atualizar a tabela do projeto anterior? 1- sim, 2- não\n")
    if atualizar == '1':
        atualizar = True
        break
    elif atualizar == '2':
        atualizar = False
        break
    else:
        print("Digite apenas o numero 1 ou 2")
        continue

if atualizar == True:
    lista_projetos = os.listdir('.')
    print(os.listdir('.'))
    while True:
        nome_projeto = input("Digite o nome do projeto para atualizar\n")
        if nome_projeto[-5:] == '_proj':
            nome_projeto = nome_projeto[:-5]
        try:
            resultados_materias = atualizar_materia_legislativa(nome_projeto+'_proj/'+nome_projeto+"_resultado_final"+".csv")
        except:
            print('Certifique que o nome do projeto foi digitado corretamente')
            continue
        break

else:
    nome_projeto = criacao_projeto(nova_tabela)

    #validacao das palavras chave
    palavras = importar_palavras()
    palavras = preparar_termos(palavras)
    print('realizando a busca para termos:\n')
    for i in palavras:
        print(i)
    #dividir as palavras em em 3 grupos

    #CASAS LEGISLATIVAS
    restricao = input('Deseja restringir a busca a sul e sudeste?\n1-sim\n2-não')
    if int(restricao) == 1:
        casas_resultado = setup_casas(nome_projeto, estado=True)
    else:
        casas_resultado = setup_casas(nome_projeto)


    #setup de busca (define se limitaremos a busca a 50 casas)
    casas_resultado = setup_busca(casas_resultado)

    #aqui chamamos o buscador com buscar_resultado() e gravamos eles crus na tabela de resultados
    resultados = buscar_resultados(casas_resultado, palavras) #limitar palavras pra teste
    #dividir isso em 3 threads
    #juntar as três num mesmo "resultados"

    with open(nome_projeto+'_proj/'+nome_projeto+'_resultados_crus_casas'+'.csv', 'a', encoding="UTF-8") as file:
        writer = csv.writer(file)
        for i in resultados:
            writer.writerow(i)

    #aqui trazemos os links da planilha de resultados da busca para a plailha de links achados
    #montar_tabela_links('links_achados')
    links_materias = raspar_resultados(nome_projeto+'_proj/'+nome_projeto+'_resultados_crus_casas'+'.csv')
    df = pd.DataFrame(links_materias)
    df.to_csv(nome_projeto+'_proj/'+nome_projeto+"_links_totais"+".csv")

    #aqui trazemos os dados da planilha de links para a planilha de materias legislativas
    #montar_tabela_conteudos('conteudos_materias')
    resultados_materias = raspar_materia_legislativa(nome_projeto+'_proj/'+nome_projeto+"_links_totais"+".csv")

#print(resultados[0:1])
df = pd.DataFrame(resultados_materias)
df.to_csv(nome_projeto+'_proj/'+nome_projeto+"_materias_legislativas"+".csv")
#columns=['Link Materia','Link Casa','titulo','ementa','ano','data','numero','observacao','assuntos']
if atualizar == False:
    df = tratamento_resultados(nome_projeto+'_proj/'+nome_projeto+"_materias_legislativas"+".csv")
    df.to_csv(nome_projeto+'_proj/'+nome_projeto+"_resultado_final"+".csv")
elif atualizar ==True:
    df = tratamento_resultados(nome_projeto+'_proj/'+nome_projeto+"_materias_legislativas"+".csv")
    today = datetime.now()
    today = today.strftime("%d_%m_%Y")
    df.to_csv(nome_projeto+'_proj/'+nome_projeto+"_resultado_final"+"_ATUALIZADO_"+today+".csv")