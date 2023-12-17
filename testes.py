from raspador import raspar_materia_legislativa
import pandas as pd
from palavras_chave import importar_palavras

resultados = raspar_materia_legislativa("./arquivos_csv/Educacaolinks_totais.csv")
df = pd.DataFrame(resultados)
df.to_csv('./arquivos_csv/conteudos_materias.csv')


def testar_palavras():
    palavras = importar_palavras()
    print('realizando a busca para termos:\n')
    for i in palavras:
        i.replace(" ", "+")
        print(i)