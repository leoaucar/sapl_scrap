"""Criação da pasta de um projeto e das suas tabelas iniciais."""
import pandas as pd
import os
import shutil


def criacao_projeto(nova_tabela, nome_padrao=True, nome_antigo=None):
    """Pergunta o nome do projeto e cria a pasta `<nome>_proj/`.

    Se `nova_tabela` for False, copia `arquivos_csv/casas_resultado.csv`
    para o projeto, para reaproveitar o teste de casas anterior.
    Retorna o nome do projeto.
    """
    # `nome_padrao` e `nome_antigo` ainda não são usados
    # (ideia: nome automático "<antigo>_atualizacao_<data>")
    nome = input('Defina o nome do projeto\n')
    os.mkdir('./'+nome+'_proj/')
    if nova_tabela == False:
        shutil.copyfile('./arquivos_csv/casas_resultado.csv', './'+nome+'_proj/'+'casas_resultado'+'.csv')
    montar_tabela_busca(nome, nome+'_resultados_crus_casas')
    return nome


def montar_tabela_busca(nome_projeto, nome_tabela):
    """Cria o CSV (só o cabeçalho) que recebe o HTML bruto das buscas."""
    df = pd.DataFrame(columns=['Indice', 'Casa', 'Palavra', 'Pagina', 'html', 'link'])
    df.to_csv('./'+nome_projeto+'_proj/'+nome_tabela+'.csv', index=False)


# As duas funções abaixo não são usadas atualmente.

def montar_tabela_links(nome_csv):
    df = pd.DataFrame(columns=['Indice', 'Casa', 'Palavra', 'link_materia'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv', index=False)


def montar_tabela_conteudos(nome_csv):
    df = pd.DataFrame(columns=['Indice', 'Casa', 'Palavra', 'link_materia', 'Titulo', 'Ementa'])
    df.to_csv('./arquivos_csv/'+nome_csv+'.csv', index=False)
