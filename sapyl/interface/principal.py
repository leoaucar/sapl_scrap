"""Ponto de entrada do programa.

Uso: sapyl (depois de `pip install .`), python -m sapyl ou python programa.py

Fluxo de um projeto novo (ou retomado):
  1. pasta `<nome>_proj/` e configuração (perguntas, salvas em config.json)
  2. casas legislativas: tabela reaproveitada ou URLs testadas de novo
  3. busca das palavras em cada casa (páginas gravadas na hora)
  4. links das matérias, sem repetição
  5. raspagem de cada matéria (API do SAPL ou página HTML)
  6. tabela final `<nome>_resultado_final.csv`
  7. (opcional) download dos textos originais
  8. resumo

Cada etapa registra o progresso em `<nome>_estado.csv`; rodar de novo e
escolher "retomar" continua de onde parou e tenta de novo o que falhou.

No modo "atualizar", as matérias de um `_resultado_final.csv` existente são
raspadas de novo, com saída em arquivos `_ATUALIZADO_<data>`.
"""

import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from sapyl import __version__, registro
from sapyl import casas as cl
from sapyl import projeto as gp
from sapyl.busca import buscar, buscas_pendentes, chave_busca
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import COLUNAS_ORIGEM, ETAPA_BUSCA
from sapyl.downloads import baixar_todos
from sapyl.estado import Estado
from sapyl.interface.entrada import (
    Leitor,
    abrir_ou_criar,
    escolher_projeto_existente,
    perguntar_opcao,
    perguntar_sim_nao,
)
from sapyl.links import deduplicar_links, ler_links, raspar_resultados, salvar_links
from sapyl.materias import raspar_todas
from sapyl.palavras import importar_palavras, preparar_termos
from sapyl.tabela import ler_final, montar_final, salvar_final

PERGUNTA_ATUALIZAR = 'Deseja apenas atualizar a tabela de algum projeto anterior? 1- sim, 2- não\n'
PERGUNTA_TABELA = 'Deseja usar a mesma tabela de casas do último projeto? 1- sim, 2- não\n'
PERGUNTA_SUL = 'Deseja restringir a busca a Sul e Sudeste? 1- sim, 2- não\n'
PERGUNTA_DOWNLOAD = 'Deseja baixar os textos originais (PDFs)? 1- sim, 2- não\n'
# Horários das requisições recentes de cada site, compartilhados entre
# execuções e projetos (veja cliente_http). Fica na pasta de trabalho.
ARQUIVO_HISTORICO = '.sapl_historico.json'
MENSAGEM_INTERROMPIDO = (
    '\nExecução interrompida. Para continuar de onde parou, rode o programa '
    'de novo, digite o mesmo nome de projeto e escolha "retomar".'
)

log = registro.logger()


def _pasta_csv(raiz: str | Path) -> Path:
    return Path(raiz) / 'arquivos_csv'


def perguntar_configuracao(raiz: str | Path, entrada: Leitor = input) -> dict[str, Any]:
    """Perguntas de um projeto novo. Devolve o dict salvo em config.json."""
    tabela_global = _pasta_csv(raiz) / 'casas_resultado.csv'
    reusar = tabela_global.exists() and perguntar_sim_nao(PERGUNTA_TABELA, entrada)
    sul_sudeste = perguntar_sim_nao(PERGUNTA_SUL, entrada)
    limite = perguntar_opcao(cl.PERGUNTA_LIMITE, list(cl.OPCOES_LIMITE), entrada)
    downloads = perguntar_sim_nao(PERGUNTA_DOWNLOAD, entrada)
    palavras = preparar_termos(importar_palavras(_pasta_csv(raiz)))
    return {
        'palavras': palavras,
        'reusar_tabela': reusar,
        'sul_sudeste': sul_sudeste,
        'limite': limite,
        'downloads': downloads,
    }


def preparar_casas(
    projeto: gp.Projeto, config: dict[str, Any], cliente: ClienteSAPL, raiz: str | Path
) -> pd.DataFrame:
    """Tabela de casas do projeto. Na retomada, usa a que já foi salva no projeto."""
    planilha = _pasta_csv(raiz) / 'casas_legislativas.xlsx'
    if projeto.casas.exists():
        return cl.ler_tabela_casas(projeto.casas, planilha)
    tabela_global = _pasta_csv(raiz) / 'casas_resultado.csv'
    testadas = config['reusar_tabela'] and tabela_global.exists()
    if testadas:
        casas = cl.ler_tabela_casas(tabela_global, planilha)
    else:
        casas = cl.importar_casas(planilha)
    if config['sul_sudeste']:
        casas = cl.filtrar_sul_sudeste(casas)
    casas = cl.limitar_casas(casas, config['limite'])
    if not testadas:
        log.info('Testando %d casas legislativas', len(casas))
        casas = cl.testar_casas(casas, cliente)
        # A tabela geral só é trocada quando todas as casas foram testadas
        if not config['sul_sudeste'] and config['limite'] == '1':
            cl.salvar_tabela_casas(casas, tabela_global)
    cl.salvar_tabela_casas(casas, projeto.casas)
    log.info('Casas: %d, das quais %d no ar', len(casas), int(casas['ativa'].sum()))
    return casas


def executar_projeto(
    projeto: gp.Projeto, config: dict[str, Any], cliente: ClienteSAPL, raiz: str | Path
) -> str:
    """Executa (ou retoma) um projeto do começo ao fim. Devolve o texto do resumo."""
    estado = Estado(projeto.estado)
    try:
        casas = preparar_casas(projeto, config, cliente, raiz)
        palavras = config['palavras']
        if buscas_pendentes(casas, palavras, estado) or not projeto.links.exists():
            buscar(casas, palavras, cliente, estado, projeto.cru)
            brutos = raspar_resultados(projeto.cru) if projeto.cru.exists() else []
            links = deduplicar_links(brutos)
            salvar_links(links, projeto.links)
            log.info('Links de matérias: %d encontrados, %d únicos', len(brutos), len(links))
        else:
            links = ler_links(projeto.links)
        raspar_todas(links, cliente, estado, projeto.materias)
        final = montar_final(projeto.materias, links)
        if config['downloads']:
            final = baixar_todos(final, str(projeto.downloads), cliente, estado)
        salvar_final(final, projeto.final)
        ativas = casas[casas['ativa']]['url']
        buscas = [
            (casa, estado.status(ETAPA_BUSCA, chave_busca(casa, p)) or 'não feita')
            for casa in ativas
            for p in palavras
        ]
        return registro.resumo(
            estado,
            links,
            projeto.final,
            buscas=buscas,
            casas_inativas=int((~casas['ativa']).sum()),
            downloads=config['downloads'],
        )
    finally:
        estado.fechar()


def executar_atualizacao(
    raiz: str | Path, cliente: ClienteSAPL, entrada: Leitor = input, hoje: str | None = None
) -> str:
    """Modo atualização: raspa de novo as matérias de um resultado final existente."""
    base = escolher_projeto_existente(raiz, entrada)
    downloads = perguntar_sim_nao(PERGUNTA_DOWNLOAD, entrada)
    hoje = hoje or datetime.now().strftime('%d_%m_%Y')
    projeto = gp.Projeto(raiz, base.nome, data=hoje)
    registro.configurar(projeto.pasta, projeto.nome)
    log.info('Atualizando o projeto %s a partir de %s', projeto.nome, base.final)
    tabela = ler_final(base.final)
    if 'Palavras' not in tabela.columns:
        tabela['Palavras'] = ''
    links = deduplicar_links(tabela[COLUNAS_ORIGEM].to_dict('records'))
    estado = Estado(projeto.estado)
    try:
        raspar_todas(links, cliente, estado, projeto.materias)
        final = montar_final(projeto.materias, links)
        if downloads:
            final = baixar_todos(final, str(projeto.downloads), cliente, estado)
        salvar_final(final, projeto.final)
        return registro.resumo(estado, links, projeto.final, downloads=downloads)
    finally:
        estado.fechar()


def main(
    entrada: Leitor = input, cliente: ClienteSAPL | None = None, raiz: str | Path = '.'
) -> int:
    """Pergunta o modo e roda o projeto (novo, retomado ou atualização).

    Devolve o código de saída: 0, ou 1 se a execução foi interrompida.
    """
    raiz = Path(raiz)
    cliente = cliente or ClienteSAPL(historico=str(raiz / ARQUIVO_HISTORICO))
    try:
        if perguntar_sim_nao(PERGUNTA_ATUALIZAR, entrada):
            texto = executar_atualizacao(raiz, cliente, entrada)
        else:
            projeto, novo = abrir_ou_criar(raiz, entrada)
            registro.configurar(projeto.pasta, projeto.nome)
            config = None if novo else gp.carregar_config(projeto)
            if config is None:
                config = perguntar_configuracao(raiz, entrada)
                gp.salvar_config(projeto, config)
            else:
                log.info('Retomando o projeto %s', projeto.nome)
            log.info('Buscando os termos: %s', ', '.join(config['palavras']))
            texto = executar_projeto(projeto, config, cliente, raiz)
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C a qualquer momento, ou Ctrl+D / fim da entrada numa pergunta
        print(MENSAGEM_INTERROMPIDO)
        return 1
    log.info(texto)
    return 0


USO = 'Uso: sapyl [--version]\nSem argumentos, o programa faz as perguntas no terminal.'


def executar(argumentos: Sequence[str] | None = None) -> int:
    """Comando `sapyl`. Só aceita `--version`; as opções de linha de comando vêm depois."""
    argumentos = sys.argv[1:] if argumentos is None else list(argumentos)
    if argumentos == ['--version']:
        print(f'sapyl {__version__}')
        return 0
    if argumentos:
        print(USO)
        return 2
    return main()


if __name__ == '__main__':
    sys.exit(executar())
