"""Perguntas no terminal, com validação (nenhuma resposta inválida derruba o programa).

`entrada` é a função que lê a resposta (por padrão, `input`); os testes passam
uma função que devolve respostas roteirizadas.
"""

from collections.abc import Callable, Sequence
from pathlib import Path

from sapyl.projeto import Projeto, nome_limpo, projetos_existentes

# Função que mostra a pergunta e devolve a resposta (`input`, ou um roteiro nos testes)
Leitor = Callable[[str], str]


def perguntar_opcao(texto: str, opcoes: Sequence[object], entrada: Leitor = input) -> str:
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


def perguntar_sim_nao(texto: str, entrada: Leitor = input) -> bool:
    """Pergunta com as opções '1- sim, 2- não'. Devolve True para sim."""
    return perguntar_opcao(texto, ['1', '2'], entrada) == '1'


def perguntar_texto(texto: str, entrada: Leitor = input, aceitar_barras: bool = False) -> str:
    """Texto não vazio. Sem barras, a menos que `aceitar_barras` (caminhos de arquivo)."""
    while True:
        resposta = str(entrada(texto)).strip()
        if not resposta:
            print('A resposta não pode ficar vazia.')
        elif not aceitar_barras and ('/' in resposta or '\\' in resposta):
            print('Não use barras ( / ou \\ ) no nome.')
        else:
            return resposta


def abrir_ou_criar(raiz: str | Path, entrada: Leitor = input) -> tuple[Projeto, bool]:
    """Pergunta o nome; cria o projeto ou, se já existe, oferece retomá-lo.

    Devolve (Projeto, novo). Nunca sobrescreve um projeto existente.
    """
    while True:
        nome = nome_limpo(perguntar_texto('Defina o nome do projeto\n', entrada))
        projeto = Projeto(raiz, nome)
        if not projeto.pasta.exists():
            projeto.pasta.mkdir(parents=True)
            return projeto, True
        escolha = perguntar_opcao(
            f'O projeto "{nome}" já existe.\n1- retomar este projeto\n2- escolher outro nome\n',
            ['1', '2'],
            entrada,
        )
        if escolha == '1':
            return projeto, False


def escolher_projeto_existente(raiz: str | Path, entrada: Leitor = input) -> Projeto:
    """Para o modo atualização: pergunta até achar um projeto com resultado final."""
    existentes = projetos_existentes(raiz)
    if existentes:
        print('Projetos encontrados: ' + ', '.join(existentes))
    while True:
        nome = nome_limpo(perguntar_texto('Digite o nome do projeto para atualizar\n', entrada))
        projeto = Projeto(raiz, nome)
        if projeto.final.exists():
            return projeto
        print(f'Não encontrei {projeto.final}. Confira o nome do projeto.')


PERGUNTA_ENTRADA_AUTORIA = (
    'Digite o nome de um projeto ou o caminho de um arquivo CSV (com a coluna Link Materia)\n'
)


def resultado_mais_recente(projeto: Projeto) -> Path | None:
    """O resultado final do projeto, ou o `_ATUALIZADO_` mais novo, se houver um."""
    candidatos = [
        projeto.final,
        *projeto.pasta.glob(f'{projeto.nome}_resultado_final_ATUALIZADO_*.csv'),
    ]
    existentes = [c for c in candidatos if c.is_file()]
    return max(existentes, key=lambda c: c.stat().st_mtime) if existentes else None


def escolher_entrada_autoria(
    raiz: str | Path, entrada: Leitor = input
) -> tuple[Path, Projeto | None]:
    """Pergunta até receber um projeto com resultado ou um CSV que existe.

    Devolve (planilha de entrada, projeto ou None se a entrada é um CSV avulso).
    """
    existentes = projetos_existentes(raiz)
    if existentes:
        print('Projetos encontrados: ' + ', '.join(existentes))
    while True:
        resposta = perguntar_texto(PERGUNTA_ENTRADA_AUTORIA, entrada, aceitar_barras=True)
        projeto = Projeto(raiz, nome_limpo(resposta))
        if projeto.pasta.is_dir():
            final = resultado_mais_recente(projeto)
            if final is not None:
                return final, projeto
        caminho = Path(resposta).expanduser()
        if not caminho.is_absolute():
            caminho = Path(raiz) / caminho
        if caminho.is_file() and caminho.suffix.lower() == '.csv':
            return caminho, None
        print(f'Não encontrei o projeto nem o arquivo "{resposta}". Confira o nome.')
