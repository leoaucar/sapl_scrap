"""Perguntas no terminal, com validação (nenhuma resposta inválida derruba o programa).

`entrada` é a função que lê a resposta (por padrão, `input`); os testes passam
uma função que devolve respostas roteirizadas.
"""


def perguntar_opcao(texto, opcoes, entrada=input):
    """Repete a pergunta até a resposta ser uma das `opcoes`. Devolve a opção (str)."""
    opcoes = [str(o) for o in opcoes]
    if len(opcoes) > 1:
        lista = ', '.join(opcoes[:-1]) + ' ou ' + opcoes[-1]
    else:
        lista = opcoes[0]
    while True:
        resposta = str(entrada(texto)).strip()
        if resposta in opcoes:
            return resposta
        print(f'Digite apenas {lista}.')


def perguntar_sim_nao(texto, entrada=input):
    """Pergunta com as opções '1- sim, 2- não'. Devolve True para sim."""
    return perguntar_opcao(texto, ['1', '2'], entrada) == '1'


def perguntar_texto(texto, entrada=input):
    """Texto não vazio, sem barras (usado para nomes de projeto e de arquivo)."""
    while True:
        resposta = str(entrada(texto)).strip()
        if not resposta:
            print('A resposta não pode ficar vazia.')
        elif '/' in resposta or '\\' in resposta:
            print('Não use barras ( / ou \\ ) no nome.')
        else:
            return resposta
