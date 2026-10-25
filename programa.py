"""Ponto de entrada do raspador SAPL.

Uso: python programa.py

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
from datetime import datetime
from pathlib import Path
import sys

from buscador import buscar, buscas_pendentes, chave_busca
import casas_legislativas as cl
from download_pdf import baixar_todos
from entrada import perguntar_opcao, perguntar_sim_nao
from estado import Estado
import gerenciador_projetos as gp
from http_sapl import ClienteSAPL
from materias import deduplicar_links, ler_links, raspar_todas, salvar_links
from palavras_chave import importar_palavras, preparar_termos
from raspador import raspar_resultados
import registro
from tratamento_resultado import ler_final, montar_final, salvar_final

PERGUNTA_ATUALIZAR = 'Deseja apenas atualizar a tabela de algum projeto anterior? 1- sim, 2- não\n'
PERGUNTA_TABELA = 'Deseja usar a mesma tabela de casas do último projeto? 1- sim, 2- não\n'
PERGUNTA_SUL = 'Deseja restringir a busca a Sul e Sudeste? 1- sim, 2- não\n'
PERGUNTA_DOWNLOAD = 'Deseja baixar os textos originais (PDFs)? 1- sim, 2- não\n'
MENSAGEM_INTERROMPIDO = ('\nExecução interrompida. Para continuar de onde parou, rode o programa '
                         'de novo, digite o mesmo nome de projeto e escolha "retomar".')

log = registro.logger()


def _pasta_csv(raiz):
    return Path(raiz) / 'arquivos_csv'


def perguntar_configuracao(raiz, entrada=input):
    """Perguntas de um projeto novo. Devolve o dict salvo em config.json."""
    tabela_global = _pasta_csv(raiz) / 'casas_resultado.csv'
    reusar = tabela_global.exists() and perguntar_sim_nao(PERGUNTA_TABELA, entrada)
    sul_sudeste = perguntar_sim_nao(PERGUNTA_SUL, entrada)
    limite = perguntar_opcao(cl.PERGUNTA_LIMITE, list(cl.OPCOES_LIMITE), entrada)
    downloads = perguntar_sim_nao(PERGUNTA_DOWNLOAD, entrada)
    palavras = preparar_termos(importar_palavras(_pasta_csv(raiz)))
    return {'palavras': palavras, 'reusar_tabela': reusar, 'sul_sudeste': sul_sudeste,
            'limite': limite, 'downloads': downloads}


def preparar_casas(projeto, config, cliente, raiz):
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


def executar_projeto(projeto, config, cliente, raiz):
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
        buscas = [(casa, estado.status('busca', chave_busca(casa, p)) or 'não feita')
                  for casa in ativas for p in palavras]
        return registro.resumo(estado, links, projeto.final, buscas=buscas,
                               casas_inativas=int((~casas['ativa']).sum()),
                               downloads=config['downloads'])
    finally:
        estado.fechar()


def executar_atualizacao(raiz, cliente, entrada=input, hoje=None):
    """Modo atualização: raspa de novo as matérias de um resultado final existente."""
    base = gp.escolher_projeto_existente(raiz, entrada)
    downloads = perguntar_sim_nao(PERGUNTA_DOWNLOAD, entrada)
    hoje = hoje or datetime.now().strftime('%d_%m_%Y')
    projeto = gp.Projeto(raiz, base.nome, data=hoje)
    registro.configurar(projeto.pasta, projeto.nome)
    log.info('Atualizando o projeto %s a partir de %s', projeto.nome, base.final)
    tabela = ler_final(base.final)
    if 'Palavras' not in tabela.columns:
        tabela['Palavras'] = ''
    links = deduplicar_links(tabela[['Link Materia', 'Link Casa', 'Palavras']].to_dict('records'))
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


def main(entrada=input, cliente=None, raiz='.'):
    raiz = Path(raiz)
    cliente = cliente or ClienteSAPL()
    try:
        if perguntar_sim_nao(PERGUNTA_ATUALIZAR, entrada):
            texto = executar_atualizacao(raiz, cliente, entrada)
        else:
            projeto, novo = gp.abrir_ou_criar(raiz, entrada)
            registro.configurar(projeto.pasta, projeto.nome)
            config = None if novo else gp.carregar_config(projeto)
            if config is None:
                config = perguntar_configuracao(raiz, entrada)
                gp.salvar_config(projeto, config)
            else:
                log.info('Retomando o projeto %s', projeto.nome)
            log.info('Buscando os termos: %s', ', '.join(config['palavras']))
            texto = executar_projeto(projeto, config, cliente, raiz)
    except KeyboardInterrupt:
        print(MENSAGEM_INTERROMPIDO)
        return 1
    log.info(texto)
    return 0


if __name__ == '__main__':
    sys.exit(main())
