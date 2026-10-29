"""Ponto de entrada do programa.

Uso: sapyl (depois de `pip install .`), python -m sapyl ou python programa.py

Fluxo de um projeto novo (ou retomado):
  1. pasta `<nome>_proj/` e configuração (perguntas, salvas em config.json)
  2. casas legislativas: tabela reaproveitada ou URLs testadas de novo
  3. para cada casa, várias ao mesmo tempo (`paralelo` no config.json):
     busca das palavras (páginas gravadas na hora), links das matérias sem
     repetição, raspagem de cada matéria (API do SAPL ou página HTML) e, se
     pedido, download dos textos originais
  4. lista de links `<nome>_links_totais.csv`, na ordem da tabela de casas
  5. tabela final `<nome>_resultado_final.csv` (a mesma de uma casa por vez)
  6. resumo

Cada etapa registra o progresso em `<nome>_estado.csv`; rodar de novo e
escolher "retomar" continua de onde parou e tenta de novo o que falhou.

No modo "atualizar", as matérias de um `_resultado_final.csv` existente são
raspadas de novo, com saída em arquivos `_ATUALIZADO_<data>`.
"""

import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from sapyl import __version__, autoria, execucao, padroes, registro
from sapyl import casas as cl
from sapyl import projeto as gp
from sapyl.busca import buscar_casa, buscas_pendentes, chave_busca, enderecos_de_busca
from sapyl.cliente_http import ClienteSAPL, resolver_servidor
from sapyl.colunas import (
    COLUNAS_MATERIAS,
    COLUNAS_ORIGEM,
    COLUNAS_PAGINAS,
    ETAPA_BUSCA,
    ETAPA_MATERIA,
    Linha,
)
from sapyl.downloads import baixar_da_casa, preencher_downloads
from sapyl.estado import ArquivoCSV, Cache, Estado
from sapyl.interface.entrada import (
    Leitor,
    abrir_ou_criar,
    escolher_entrada_autoria,
    escolher_projeto_existente,
    perguntar_opcao,
    perguntar_sim_nao,
)
from sapyl.links import (
    agrupar_por_casa,
    deduplicar_links,
    host,
    ler_links,
    links_das_buscas,
    ordenar_por_casa,
    salvar_links,
)
from sapyl.materias import Fontes, raspar_pendentes
from sapyl.palavras import importar_palavras, preparar_termos
from sapyl.tabela import (
    COLUNA_RELEVANTE,
    colunas_extras,
    filtrar_relevantes,
    juntar_colunas_extras,
    ler_final,
    montar_final,
    salvar_final,
    ultimas_raspagens,
)

BOAS_VINDAS = f'{registro.NOME} (versão {__version__})\n'
PERGUNTA_MODO = (
    'O que você quer fazer?\n'
    '1- novo projeto ou retomar um projeto\n'
    '2- atualizar um projeto\n'
    '3- autoria e tramitação\n'
)
PERGUNTA_TABELA = 'Deseja usar a mesma tabela de casas do último projeto? 1- sim, 2- não\n'
PERGUNTA_SUL = 'Deseja restringir a busca a Sul e Sudeste? 1- sim, 2- não\n'
PERGUNTA_RELEVANTES = (
    'Atualizar só as matérias marcadas como relevantes (coluna Relevante)? 1- sim, 2- não\n'
)
PERGUNTA_DOWNLOAD = 'Deseja baixar os textos originais (PDFs)? 1- sim, 2- não\n'
# Horários das requisições recentes de cada site, compartilhados entre
# execuções e projetos (veja cliente_http). Fica na pasta de trabalho.
ARQUIVO_HISTORICO = '.sapl_historico.json'
MENSAGEM_INTERROMPIDO_AUTORIA = (
    '\nExecução interrompida. Para continuar de onde parou, rode o programa de novo, '
    'escolha 3 e digite a mesma entrada.'
)
MENSAGEM_INTERROMPIDO = (
    '\nExecução interrompida. Para continuar de onde parou, rode o programa '
    'de novo, digite o mesmo nome de projeto e escolha "retomar".'
)

MENSAGEM_CONFIG_INVALIDA = (
    '\nConfiguração inválida em {erro}\n'
    'Corrija o valor (ou apague a chave "paralelo" para usar os padrões) e rode de novo.'
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
        padroes.CHAVE_PARALELO: padroes.padroes_paralelo(),
    }


def ler_paralelo(
    projeto: gp.Projeto | None, config: dict[str, Any] | None = None
) -> dict[str, int]:
    """`paralelo` do config.json do projeto, conferido e completado com os padrões.

    Projeto de versão antiga (sem `paralelo` ou sem config.json) usa os
    padrões. Um valor inválido lança `padroes.ConfiguracaoInvalida`, com o
    caminho do arquivo na mensagem, antes de qualquer requisição.
    """
    if config is None and projeto is not None:
        config = gp.carregar_config(projeto)
    try:
        return padroes.validar_paralelo((config or {}).get(padroes.CHAVE_PARALELO))
    except padroes.ConfiguracaoInvalida as erro:
        onde = projeto.config if projeto is not None else 'config.json'
        raise padroes.ConfiguracaoInvalida(f'{onde}: {erro}') from erro


def avisar_palavras_mudadas(raiz: str | Path, salvas: list[str]) -> list[str]:
    """Na retomada, avisa se o arquivo de palavras atual difere das palavras do projeto.

    O projeto continua com as palavras salvas em config.json. Devolve o texto do
    aviso (linhas), ou [] se as palavras são iguais ou não há arquivo de palavras.
    """
    pasta = _pasta_csv(raiz)
    if not any((pasta / f'palavras_chave.{ext}').exists() for ext in ('csv', 'xlsx')):
        return []
    try:
        atuais = preparar_termos(importar_palavras(pasta))
    except (OSError, ValueError, KeyError) as erro:
        log.debug('Não deu para ler o arquivo de palavras para comparar: %s', erro)
        return []
    novas = [p for p in atuais if p not in salvas]
    fora = [p for p in salvas if p not in atuais]
    if not novas and not fora:
        return []
    linhas = ['O arquivo de palavras-chave mudou desde que este projeto foi criado.']
    if novas:
        linhas.append('  Novas no arquivo (não serão buscadas): ' + ', '.join(novas))
    if fora:
        linhas.append('  Do projeto, fora do arquivo (continuam): ' + ', '.join(fora))
    linhas.append(
        '  O projeto continua com as palavras salvas. Para buscar as novas, crie um projeto novo.'
    )
    log.warning('\n'.join(linhas))
    return linhas


def preparar_cliente(cliente: ClienteSAPL, paralelo: dict[str, int]) -> float:
    """Aplica o `paralelo` do projeto ao cliente. Devolve o horário de início."""
    cliente.definir_limite_por_servidor(paralelo['limite_por_servidor'])
    return time.monotonic()


def sobre_a_execucao(cliente: ClienteSAPL, paralelo: dict[str, int], inicio: float) -> list[str]:
    """Linhas do resumo: tempo, casas ao mesmo tempo e o limite de cada servidor."""
    servidores = [
        (servidor, len(hosts), cliente.limite_por_servidor, cliente.teto(servidor))
        for servidor, hosts in sorted(cliente.servidores().items())
    ]
    return registro.linhas_da_execucao(
        time.monotonic() - inicio, paralelo['casas_ao_mesmo_tempo'], servidores
    )


def mapeador(
    cliente: ClienteSAPL, paralelo: dict[str, int], progresso: Callable[[], str] | None = None
) -> padroes.Mapear:
    """`mapear(tarefa, casas)` que roda até `casas_ao_mesmo_tempo` casas ao mesmo tempo."""

    def mapear(tarefa: Callable[[str], Any], casas: Sequence[str]) -> list[Any]:
        return execucao.por_casa(
            casas, tarefa, paralelo['casas_ao_mesmo_tempo'], cliente.parar, progresso
        )

    return mapear


def preparar_casas(
    projeto: gp.Projeto,
    config: dict[str, Any],
    cliente: ClienteSAPL,
    raiz: str | Path,
    mapear: padroes.Mapear = padroes.em_sequencia,
) -> pd.DataFrame:
    """Tabela de casas do projeto. Na retomada, usa a que já foi salva no projeto.

    As casas são testadas com `mapear` (várias ao mesmo tempo, no programa).
    """
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
        casas = cl.testar_casas(casas, cliente, mapear)
        # A tabela geral só é trocada quando todas as casas foram testadas
        if not config['sul_sudeste'] and config['limite'] == '1':
            cl.salvar_tabela_casas(casas, tabela_global)
    cl.salvar_tabela_casas(casas, projeto.casas)
    log.info('Casas: %d, das quais %d no ar', len(casas), int(casas['ativa'].sum()))
    return casas


class Raspagem:
    """Matérias (e downloads) de uma casa, com o que as casas compartilham numa execução.

    O arquivo de matérias, o estado e as fontes são os mesmos para todas as
    casas, que podem rodar ao mesmo tempo. Com `pasta_downloads`, cada casa
    baixa os seus textos logo depois das suas matérias.
    """

    def __init__(
        self,
        cliente: ClienteSAPL,
        estado: Estado,
        arquivo_materias: Path,
        fontes: Fontes,
        pasta_downloads: str | None = None,
    ) -> None:
        self.cliente = cliente
        self.estado = estado
        self.fontes = fontes
        self.pasta_downloads = pasta_downloads
        # matérias raspadas em execuções anteriores (o texto original de cada uma)
        self.anteriores = ultimas_raspagens(arquivo_materias) if pasta_downloads else {}
        self.arquivo = ArquivoCSV(arquivo_materias, COLUNAS_MATERIAS)

    def da_casa(self, links: list[Linha]) -> None:
        """Raspa as matérias pendentes de `links` (de uma casa) e baixa os textos."""
        novas = raspar_pendentes(links, self.cliente, self.estado, self.arquivo, self.fontes)
        if self.pasta_downloads is None:
            return
        recentes = {linha['chave']: linha for linha in novas}
        linhas = [recentes.get(i['chave']) or self.anteriores.get(i['chave']) for i in links]
        baixar_da_casa(
            [lin for lin in linhas if lin], self.pasta_downloads, self.cliente, self.estado
        )

    def fechar(self) -> None:
        """Fecha o arquivo de matérias."""
        self.arquivo.fechar()


def progresso_das_materias(estado: Estado) -> str:
    """Texto da linha de progresso geral: matérias raspadas e com erro até agora."""
    contagem = estado.contagens(ETAPA_MATERIA)
    return f'matérias: {contagem.get("ok", 0)} raspadas, {contagem.get("erro", 0)} com erro'


def executar_projeto(
    projeto: gp.Projeto, config: dict[str, Any], cliente: ClienteSAPL, raiz: str | Path
) -> str:
    """Executa (ou retoma) um projeto do começo ao fim. Devolve o texto do resumo.

    Cada casa faz busca, links, matérias e downloads, várias casas ao mesmo
    tempo. A lista de links e a tabela final saem na ordem da tabela de casas,
    iguais às de uma casa por vez.
    """
    paralelo = ler_paralelo(projeto, config)
    inicio = preparar_cliente(cliente, paralelo)
    estado = Estado(projeto.estado)
    try:
        casas = preparar_casas(projeto, config, cliente, raiz, mapeador(cliente, paralelo))
        palavras = config['palavras']
        ativas = list(casas[casas['ativa']]['url'])
        refazer_links = bool(buscas_pendentes(casas, palavras, estado))
        refazer_links = refazer_links or not projeto.links.exists()
        if refazer_links:
            # A lista é refeita no fim. Sem ela, uma execução interrompida antes
            # do fim também a refaz na retomada (nunca fica uma lista velha).
            projeto.links.unlink(missing_ok=True)
            conhecidos = agrupar_por_casa(links_das_buscas(projeto.paginas, projeto.cru))
        else:
            conhecidos = agrupar_por_casa(ler_links(projeto.links))
        com_busca = {host(u) for u in ativas}
        # links de casas que não estão no ar agora (projetos antigos): só a raspagem
        fila = ativas + [g[0]['Link Casa'] for h, g in conhecidos.items() if h not in com_busca]
        enderecos = enderecos_de_busca(casas)
        fontes = Fontes(Cache(projeto.cache), cl.enderecos_finais(casas))
        pasta = str(projeto.downloads) if config['downloads'] else None
        raspagem = Raspagem(cliente, estado, projeto.materias, fontes, pasta)
        paginas = ArquivoCSV(projeto.paginas, COLUNAS_PAGINAS) if refazer_links else None

        def pipeline(casa: str) -> None:
            links_casa = conhecidos.get(host(casa), [])
            if paginas is not None and host(casa) in com_busca:
                novos = buscar_casa(casa, palavras, cliente, estado, paginas, enderecos.get(casa))
                links_casa = deduplicar_links(links_casa + novos)
            raspagem.da_casa(links_casa)

        log.info(
            'Casas a processar: %d, até %d ao mesmo tempo',
            len(fila),
            paralelo['casas_ao_mesmo_tempo'],
        )
        try:
            mapeador(cliente, paralelo, lambda: progresso_das_materias(estado))(pipeline, fila)
        finally:
            raspagem.fechar()
            if paginas is not None:
                paginas.fechar()
        if refazer_links:
            brutos = links_das_buscas(projeto.paginas, projeto.cru)
            links = deduplicar_links(ordenar_por_casa(brutos, casas['url']))
            salvar_links(links, projeto.links)
            log.info('Links de matérias: %d encontrados, %d únicos', len(brutos), len(links))
        else:
            links = ler_links(projeto.links)
        final = montar_final(projeto.materias, links)
        if config['downloads']:
            final = preencher_downloads(final, estado, str(projeto.downloads))
        salvar_final(final, projeto.final)
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
            execucao=sobre_a_execucao(cliente, paralelo, inicio),
        )
    finally:
        estado.fechar()


def executar_atualizacao(
    raiz: str | Path, cliente: ClienteSAPL, entrada: Leitor = input, hoje: str | None = None
) -> str:
    """Modo atualização: raspa de novo as matérias de um resultado final existente.

    As colunas acrescentadas à mão no resultado (ex.: `Relevante`, anotações)
    passam para o arquivo novo. Se houver a coluna `Relevante`, pergunta se é
    para atualizar só as matérias marcadas.
    """
    base = escolher_projeto_existente(raiz, entrada)
    paralelo = ler_paralelo(base)
    tabela = ler_final(base.final)
    so_relevantes = COLUNA_RELEVANTE in tabela.columns and perguntar_sim_nao(
        PERGUNTA_RELEVANTES, entrada
    )
    downloads = perguntar_sim_nao(PERGUNTA_DOWNLOAD, entrada)
    inicio = preparar_cliente(cliente, paralelo)
    hoje = hoje or datetime.now().strftime('%d_%m_%Y')
    projeto = gp.Projeto(raiz, base.nome, data=hoje)
    registro.configurar(projeto.pasta, projeto.nome, 'atualizacao')
    log.info('Atualizando o projeto %s a partir de %s', projeto.nome, base.final)
    extras = colunas_extras(tabela)
    if extras:
        log.info('Colunas acrescentadas mantidas: %s', ', '.join(extras))
    if so_relevantes:
        total = len(tabela)
        tabela = filtrar_relevantes(tabela)
        log.info('Só as relevantes: %d de %d matérias', len(tabela), total)
    if 'Palavras' not in tabela.columns:
        tabela['Palavras'] = ''
    links = deduplicar_links(tabela[COLUNAS_ORIGEM].to_dict('records'))
    estado = Estado(projeto.estado)
    # as casas do projeto dizem quais sites redirecionam
    finais = (
        cl.enderecos_finais(cl.ler_tabela_casas(projeto.casas)) if projeto.casas.exists() else {}
    )
    try:
        fontes = Fontes(Cache(projeto.cache), finais)
        pasta = str(projeto.downloads) if downloads else None
        raspagem = Raspagem(cliente, estado, projeto.materias, fontes, pasta)
        grupos = agrupar_por_casa(links)
        fila = [g[0]['Link Casa'] for g in grupos.values()]
        mapear = mapeador(cliente, paralelo, lambda: progresso_das_materias(estado))
        try:
            mapear(lambda casa: raspagem.da_casa(grupos[host(casa)]), fila)
        finally:
            raspagem.fechar()
        final = montar_final(projeto.materias, links)
        if downloads:
            final = preencher_downloads(final, estado, str(projeto.downloads))
        salvar_final(juntar_colunas_extras(final, tabela), projeto.final)
        return registro.resumo(
            estado,
            links,
            projeto.final,
            downloads=downloads,
            execucao=sobre_a_execucao(cliente, paralelo, inicio),
        )
    finally:
        estado.fechar()


def executar_autoria(raiz: str | Path, cliente: ClienteSAPL, entrada: Leitor = input) -> str:
    """Autoria e tramitação de um projeto (o resultado mais recente) ou de um CSV.

    Saída, estado e log ficam ao lado da planilha de entrada (na pasta do
    projeto, para um projeto). Devolve o texto do resumo.
    """
    planilha, projeto = escolher_entrada_autoria(raiz, entrada)
    paralelo = ler_paralelo(projeto)
    inicio = preparar_cliente(cliente, paralelo)
    if projeto is not None:
        registro.configurar(projeto.pasta, projeto.nome, 'autoria')
        casas = cl.ler_tabela_casas(projeto.casas) if projeto.casas.exists() else None
        finais = cl.enderecos_finais(casas) if casas is not None else {}
        fontes = Fontes(Cache(projeto.cache), finais)
    else:
        registro.configurar(planilha.parent, planilha.stem, 'autoria')
        fontes = Fontes()
    log.info('Autoria e tramitação de %s', planilha)
    saida, contagens = autoria.processar(planilha, cliente, fontes, mapeador(cliente, paralelo))
    return registro.resumo_autoria(
        contagens, saida, execucao=sobre_a_execucao(cliente, paralelo, inicio)
    )


def main(
    entrada: Leitor = input, cliente: ClienteSAPL | None = None, raiz: str | Path = '.'
) -> int:
    """Pergunta o modo e roda: projeto novo ou retomado, atualização, ou autoria e tramitação.

    Devolve o código de saída: 0; 1 se a execução foi interrompida; 2 se o
    `paralelo` do config.json do projeto tem um valor inválido.
    """
    raiz = Path(raiz)
    # O servidor (IP) de cada site, para o limite por servidor (veja cliente_http)
    cliente = cliente or ClienteSAPL(
        historico=str(raiz / ARQUIVO_HISTORICO), servidor_de=resolver_servidor
    )
    print(BOAS_VINDAS)
    modo = None
    try:
        modo = perguntar_opcao(PERGUNTA_MODO, ['1', '2', '3'], entrada)
        if modo == '2':
            texto = executar_atualizacao(raiz, cliente, entrada)
        elif modo == '3':
            texto = executar_autoria(raiz, cliente, entrada)
        else:
            projeto, novo = abrir_ou_criar(raiz, entrada)
            registro.configurar(projeto.pasta, projeto.nome, 'novo' if novo else 'retomada')
            config = None if novo else gp.carregar_config(projeto)
            if config is None:
                config = perguntar_configuracao(raiz, entrada)
                gp.salvar_config(projeto, config)
            else:
                log.info('Retomando o projeto %s', projeto.nome)
                avisar_palavras_mudadas(raiz, config['palavras'])
            log.info('Buscando os termos: %s', ', '.join(config['palavras']))
            texto = executar_projeto(projeto, config, cliente, raiz)
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C a qualquer momento, ou Ctrl+D / fim da entrada numa pergunta
        print(MENSAGEM_INTERROMPIDO_AUTORIA if modo == '3' else MENSAGEM_INTERROMPIDO)
        return 1
    except padroes.ConfiguracaoInvalida as erro:
        print(MENSAGEM_CONFIG_INVALIDA.format(erro=erro))
        return 2
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
