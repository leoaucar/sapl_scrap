from palavras_chave import importar_palavras
from casas_legislativas import importar_casas, teste_url_ativa
from raspador import raspar_resultados, raspar_materia_legislativa
from gerenciador_projetos import criacao_projeto
from buscador import buscar_resultados
import pandas as pd
import csv

lista_casas = importar_casas()

#validacao das casas legislativas online
casas_resultado = teste_url_ativa(lista_casas[0:50]) #limitado 20 para teste
print('realizando a busca em ' + str(len(casas_resultado)) + ' casas com url ativas')

#validacao das palavras chave
palavras = importar_palavras()
print('realizando a busca para termos:\n')
for i in palavras:
    print(i)

nome_projeto = criacao_projeto()
resultados = buscar_resultados(casas_resultado, palavras)

with open('arquivos_csv/'+nome_projeto+'_busca_casas_legislativas'+'.csv', 'a', encoding="UTF-8") as file:
    writer = csv.writer(file)
    for i in resultados:
        writer.writerow(i)

#aqui trazemos os links da planilha de resultados da busca para a plailha de links achados
#montar_tabela_links('links_achados')
resultados = raspar_resultados('./arquivos_csv/'+nome_projeto+'_busca_casas_legislativas'+'.csv')
#with open('arquivos_csv/links_achados.csv', 'a', encoding="UTF-8") as file:
#    writer = csv.writer(file)
#    for i in resultados:
#        writer.writerow(i)
df = pd.DataFrame(resultados)
df.to_csv("arquivos_csv/"+nome_projeto+"_links_totais"+".csv")

#aqui trazemos os dados da planilha de links para a planilha de materias legislativas
#montar_tabela_conteudos('conteudos_materias')
resultados = raspar_materia_legislativa("arquivos_csv/"+nome_projeto+"links_totais"+".csv")
#with open('arquivos_csv/conteudo_materias.csv', 'a', encoding="UTF-8") as file:
#    writer = csv.writer(file)
#    for i in resultados:
#        writer.writerow(i)

df = pd.DataFrame(resultados)
df.to_csv("./arquivos_csv/"+nome_projeto+"_materias_legislativas"+".csv")