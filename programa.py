from palavras_chave import importar_palavras
from casas_legislativas import importar_casas, teste_url_ativa
from raspador import raspar_resultados
from gerenciador_projetos import montar_tabela_busca
from buscador import buscar_resultados
import pandas as pd
import csv

lista_casas = importar_casas()
#print(lista_casas)

#validacao das casas legislativas online
casas_resultado = teste_url_ativa(lista_casas[0:20]) #limitado 20 para teste
#print(casas_resultado)

#validacao das palavras chave
palavras = importar_palavras()
#print(palavras)

montar_tabela_busca('resultado_busca')
resultados = buscar_resultados(casas_resultado, palavras)
for i in resultados:           
    with open('arquivos_csv/resultado_busca.csv', 'a', encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(i)

resultados = raspar_resultados('./arquivos_csv/resultado_busca.csv')
df = pd.DataFrame(resultados)
df.to_csv("arquivos_csv/links_achados.csv")