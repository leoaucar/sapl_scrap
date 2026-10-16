"""Carregamento da lista de casas legislativas e teste de quais estão no ar."""
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Estados usados quando a busca é restrita a Sul e Sudeste
ESTADOS_SUL_SUDESTE = ['RJ', 'SP', 'RS', 'SC', 'MG', 'ES', 'PR']


def importar_casas(estado=False):
    """Lê `arquivos_csv/casas_legislativas.xlsx` e devolve a coluna de URLs.

    `estado=True` restringe às casas de Sul e Sudeste.
    """
    df = pd.read_excel('./arquivos_csv/casas_legislativas.xlsx')
    # Permite também passar uma lista de UFs em `estado`
    try:
        df = df[df['UF'].isin(estado)]
    except:
        pass
    if estado == True:
        df = df[df['UF'].isin(ESTADOS_SUL_SUDESTE)]
    casas = df['URL do serviço']
    return casas


def teste_url_ativa(casas):
    """Testa cada URL e devolve uma lista de tuplas (url, respondeu_200).

    Casas cujo acesso gera exceção (timeout, DNS...) ficam de fora da lista.
    """
    resultado_casas = []
    for casa in casas:
        print(casa)
        try:
            response = requests.get(casa, timeout=5)
            if response.status_code == 200:
                resultado_casas.append((casa, True))
            else:
                resultado_casas.append((casa, False))
        except:
            continue
    return resultado_casas


def teste_conteudo_atualizado(casas, palavras):
    """[INCOMPLETO / NÃO USADO] Ideia de testar se a busca de cada casa traz conteúdo.

    Não funciona como está: `response.text > 5` compara texto com número.
    """
    palavras = ['educacao', 'orcamento', 'saude']
    links_totais = []
    for casa in casas:
        for palavra in palavras:
            response = requests.get(casa + 'sistema/search/?q=' + palavra)
            soup = BeautifulSoup(response.text)
            for a in soup.find_all('a', href=True):
                links_totais.append([a['href'], palavra])
            if response.text > 5:
                print('ok')
            else:
                print('não preenchido')
    return casas


def setup_casas(nome_projeto, estado=False):
    """Prepara a lista de casas do projeto.

    - Se o projeto já tem `casas_resultado.csv` (copiado do último projeto),
      reaproveita essa tabela sem testar as casas de novo.
    - Senão, carrega a planilha de casas, testa as URLs e salva o resultado
      no projeto e em `arquivos_csv/casas_resultado.csv`.

    Retorna uma sequência de tuplas (url, ativa).
    """
    # Modo de operação:
    #   2 = reaproveitar tabela existente
    #   3 = carregar e testar todas as casas
    #   1 = (desativado) re-testar as casas da tabela existente
    try:
        casas_resultado = pd.read_csv('./'+nome_projeto+'_proj/'+'casas_resultado.csv')
        print('Última atualização continha ' + str(len(casas_resultado)) + ' casas com url ativas')
        casas_legislativas = 0
    except:
        casas_legislativas = 3

    while True:
        if casas_legislativas == 0:
            # Pergunta desativada; fixa em 2 (não re-testar)
            # casas_legislativas = input("Deseja atualizar status das casas legislativas? \nEscolha: 1 - sim 2 - não \n")
            casas_legislativas = 2
        else:
            break
        try:
            casas_legislativas = int(casas_legislativas)
            if casas_legislativas == 1 or casas_legislativas == 2:
                if casas_legislativas == 1:
                    print("Atualizando status das casas legislativas")
                    casas_resultado = teste_url_ativa(casas_resultado['0'])
                    print(casas_resultado)
                break
            else:
                print("Digite apenas o número 1 ou 2")
                continue
        except:
            print("Digite apenas o número 1 ou 2")
            continue

    if casas_legislativas == 3:
        print("Carregando Casas Legislativas")
        lista_casas = importar_casas(estado)
        casas_resultado = teste_url_ativa(lista_casas)
        print('realizando a busca em ' + str(len(casas_resultado)) + ' casas com url ativas')
        pd.DataFrame(casas_resultado).to_csv('./'+nome_projeto+'_proj/'+'/casas_resultado.csv', index=False)
        pd.DataFrame(casas_resultado).to_csv('./arquivos_csv/casas_resultado.csv', index=False)

    elif casas_legislativas == 2:
        # CSV salvo tem colunas '0' (url) e '1' (ativa); reconstrói as tuplas
        casas_resultado['tupla'] = list(zip(casas_resultado['0'], casas_resultado['1']))
        casas_resultado = casas_resultado['tupla']

    return casas_resultado
