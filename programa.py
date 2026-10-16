"""Ponto de entrada do raspador SAPL.

Fluxo de um projeto novo:
  1. cria a pasta `<nome>_proj/`
  2. carrega e formata as palavras-chave
  3. carrega/testa as casas legislativas
  4. busca as palavras em cada casa e grava o HTML bruto
  5. extrai os links das matérias e raspa cada uma
  6. limpa os dados e grava `<nome>_resultado_final.csv`
  7. (opcional) baixa os PDFs dos textos originais

No modo "atualizar", pula as etapas 1-5 e raspa de novo as matérias do
`_resultado_final.csv` de um projeto existente.

Uso: python programa.py
"""
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
from download_pdf import download_arquivo


# ---------------------------------------------------------------------------
# Perguntas iniciais
# ---------------------------------------------------------------------------
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
    atualizar = input("Deseja apenas atualizar a tabela de algum projeto anterior? 1- sim, 2- não\n")
    if atualizar == '1':
        atualizar = True
        break
    elif atualizar == '2':
        atualizar = False
        break
    else:
        print("Digite apenas o numero 1 ou 2")
        continue

# ---------------------------------------------------------------------------
# Modo atualização: raspa de novo as matérias de um projeto existente
# ---------------------------------------------------------------------------
if atualizar == True:
    print(os.listdir('.'))
    while True:
        nome_projeto = input("Digite o nome do projeto para atualizar\n")
        if nome_projeto[-5:] == '_proj':
            nome_projeto = nome_projeto[:-5]
        try:
            resultados_materias = atualizar_materia_legislativa(nome_projeto+'_proj/'+nome_projeto+"_resultado_final"+".csv")
        except:
            print('Certifique que o nome do projeto foi digitado corretamente ou o arquivo de resultados finais está presente')
            continue
        break

# ---------------------------------------------------------------------------
# Projeto novo: busca completa
# ---------------------------------------------------------------------------
else:
    # 1. Pasta do projeto (copia a tabela de casas anterior se nova_tabela=False)
    nome_projeto = criacao_projeto(nova_tabela)

    # 2. Palavras-chave
    palavras = importar_palavras()
    palavras = preparar_termos(palavras)
    print('realizando a busca para termos:\n')
    for i in palavras:
        print(i)

    # 3. Casas legislativas
    # Obs.: a restrição só tem efeito quando a tabela de casas é refeita
    restricao = input('Deseja restringir a busca a sul e sudeste?\n1-sim\n2-não')
    if int(restricao) == 1:
        casas_resultado = setup_casas(nome_projeto, estado=True)
    else:
        casas_resultado = setup_casas(nome_projeto)

    # Limite opcional de casas para teste
    casas_resultado = setup_busca(casas_resultado)

    # 4. Busca: grava o HTML bruto de cada página de resultados
    resultados = buscar_resultados(casas_resultado, palavras)
    with open(nome_projeto+'_proj/'+nome_projeto+'_resultados_crus_casas'+'.csv', 'a', encoding="UTF-8") as file:
        writer = csv.writer(file)
        for i in resultados:
            writer.writerow(i)

    # 5a. Extrai os links de matérias das páginas de busca
    links_materias = raspar_resultados(nome_projeto+'_proj/'+nome_projeto+'_resultados_crus_casas'+'.csv')
    df = pd.DataFrame(links_materias)
    df.to_csv(nome_projeto+'_proj/'+nome_projeto+"_links_totais"+".csv")

    # 5b. Raspa os dados de cada matéria
    resultados_materias = raspar_materia_legislativa(nome_projeto+'_proj/'+nome_projeto+"_links_totais"+".csv")

# ---------------------------------------------------------------------------
# 6. Tratamento e gravação do resultado final (ambos os modos)
# ---------------------------------------------------------------------------
df = pd.DataFrame(resultados_materias)
df.to_csv(nome_projeto+'_proj/'+nome_projeto+"_materias_legislativas"+".csv")

if atualizar == False:
    df = tratamento_resultados(nome_projeto+'_proj/'+nome_projeto+"_materias_legislativas"+".csv", atualizar)
    df.to_csv(nome_projeto+'_proj/'+nome_projeto+"_resultado_final"+".csv")
elif atualizar == True:
    df = tratamento_resultados(nome_projeto+'_proj/'+nome_projeto+"_materias_legislativas"+".csv", atualizar)
    today = datetime.now()
    today = today.strftime("%d_%m_%Y")
    df.to_csv(nome_projeto+'_proj/'+nome_projeto+"_resultado_final"+"_ATUALIZADO_"+today+".csv")

# ---------------------------------------------------------------------------
# 7. Download opcional dos PDFs (nomeados pelo número da linha: 0.pdf, 1.pdf...)
# ---------------------------------------------------------------------------
dowload_opcao = int(input("Deseja realizar downloads? 1-sim, 2-não"))
if dowload_opcao == 1:
    diretorio_geral = nome_projeto+'_proj/'
    if atualizar == False:
        diretorio_downloads = 'downloads'
    elif atualizar == True:
        diretorio_downloads = 'downloads'+today
    path = os.path.join(diretorio_geral, diretorio_downloads)
    os.mkdir(path)
    print("realizando downloads")
    id = 0
    for i in df['texto_original']:
        download_arquivo(i, id, path)
        id = id + 1
        print("download numero: " + str(id))
