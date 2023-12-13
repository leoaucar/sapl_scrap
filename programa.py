from palavras_chave import importar_palavras
from casas_legislativas import importar_casas, teste_url_ativa
from raspador import raspar_resultados, raspar_materia_legislativa
from gerenciador_projetos import montar_tabela_busca
from buscador import buscar_resultados
import pandas as pd
import csv

lista_casas = importar_casas()
#print(lista_casas)

#validacao das casas legislativas online
casas_resultado = teste_url_ativa(lista_casas[0:100]) #limitado 20 para teste
#print(casas_resultado)

#validacao das palavras chave
palavras = importar_palavras()
#print(palavras)

montar_tabela_busca('resultado_busca')
resultados = buscar_resultados(casas_resultado, palavras)
           
with open('arquivos_csv/resultado_busca.csv', 'a', encoding="UTF-8") as file:
    writer = csv.writer(file)
    for i in resultados:
        writer.writerow(i)

#aqui trazemos os links da planilha de resultados da busca para a plailha de links achados
resultados = raspar_resultados('./arquivos_csv/resultado_busca.csv')
df = pd.DataFrame(resultados)
df.to_csv("arquivos_csv/links_achados.csv")

#aqui trazemos os dados da planilha de links para a planilha de materias legislativas
resultados = raspar_materia_legislativa('./arquivos_csv/links_achados.csv')
df = pd.DataFrame(resultados)
df.to_csv('./arquivos_csv/conteudos_materias.csv')