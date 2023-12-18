from raspador import raspar_materia_legislativa
import pandas as pd
from palavras_chave import importar_palavras

def testar_raspagem_links():
    resultados = raspar_materia_legislativa("./arquivos_csv/Educacaolinks_totais.csv")
    df = pd.DataFrame(resultados)
    df.to_csv('./arquivos_csv/conteudos_materias.csv')


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

escolha = input('Escolha teste:\nraspagem\npalavras\n')
if escolha == 'raspagem':
    testar_raspagem_links()
elif escolha== 'palavras':
    testar_palavras()