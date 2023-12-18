import pandas as pd

def importar_palavras():
    df = pd.read_csv('./arquivos_csv/palavras_chave.csv', header=0)
    palavras = df['Palavras']
    return palavras

def preparar_termos(palavras):
    print('realizando a busca para termos:\n')
    lista_termos = []
    for palavra in palavras:
        termos = palavra.split(",")
        for termo in termos:
            n = termos.index(termo)
            termo = termo.strip()
            termo = termo.replace(" ", "+")
            termo = "\""+termo+"\""
            termos[n] = termo
        termos = "+".join(termos)
        lista_termos.append(termos)
    #lista_termos = pd.DataFrame(lista_termos)
    return lista_termos
#tratamento e teste das palavras chave
#que tipo de testes usar nas palavras chave?