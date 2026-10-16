"""Busca das palavras-chave no sistema de pesquisa de cada casa legislativa."""
import requests


def setup_busca(casas_resultado):
    """Pergunta se a busca deve ser limitada (útil para testes) e recorta a lista de casas."""
    while True:
        limite_busca = input('Deseja limitar sua busca para teste? \n1- não(pesquisar todas as casas) \n2- 50 primeiras casas \n3- 50 últimas casas\n4- Apenas 10 casas\n')
        try:
            limite_busca = int(limite_busca)
            if limite_busca > 0 and limite_busca < 6:
                break
            else:
                print("Digite apenas o número 1, 2, 3 ou 4")
                continue
        except:
            print("Digite apenas o número 1, 2, 3 ou 4")
            continue

    if limite_busca == 1:
        casas_resultado = casas_resultado
    elif limite_busca == 2:
        casas_resultado = casas_resultado[:50]
    elif limite_busca == 3:
        len_casas = len(casas_resultado)
        casas_resultado = casas_resultado[len_casas-49:len_casas]
    elif limite_busca == 4:
        casas_resultado = casas_resultado[:10]
    return casas_resultado


def buscar_resultados(casas_resultado, palavras):
    """Pesquisa cada palavra em cada casa ativa, página a página.

    `casas_resultado` é uma lista de tuplas (url_da_casa, ativa).
    Avança as páginas (`?page=N`) até o servidor responder algo diferente
    de 200. Retorna uma lista de
    [indice, url_da_casa, palavra, pagina, html, url_da_busca].
    """
    indice = 0
    urls_erro = []
    resultados = []
    numero_casa = 1
    for casa in casas_resultado:
        print("Busca na casa número: " + str(numero_casa) + " de " + str(len(casas_resultado)))
        numero_casa = numero_casa + 1
        if casa[1] != True:  # casa fora do ar no último teste
            continue
        for palavra in palavras:
            pagina = 1
            while True:
                url = casa[0] + 'sistema/search/?page=' + str(pagina) + '&q=' + palavra
                try:
                    response = requests.get(url, timeout=10)
                except:
                    # ATENÇÃO: repete a mesma URL sem limite de tentativas
                    urls_erro.append(url)
                    continue
                if response.status_code == 200:
                    print(url)
                    # TODO: separar páginas de resultado vazias das com resultados
                    resultados.append([indice, casa[0], palavra, pagina, response.text, url])
                else:
                    # fim das páginas (ou erro / limite de requisições)
                    break
                indice = indice + 1
                pagina = pagina + 1
    print(urls_erro)
    return resultados
