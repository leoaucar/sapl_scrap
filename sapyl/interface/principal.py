"""Ponto de entrada do programa.

Uso: sapyl (depois de `pip install .`), python -m sapyl ou python programa.py

Menu principal: novo projeto, retomar, atualizar, autoria e tramitação,
ajuda, sair. As perguntas são menus com as setas num terminal interativo, ou
opções numeradas (veja `perguntas.py`).

Fluxo de um projeto novo (ou retomado):
  0. palavras-chave e planilha de casas conferidas antes de qualquer pergunta;
     depois das perguntas, uma tela de confirmação (começar, mudar, cancelar)
  1. pasta `<nome>_proj/` e configuração (respostas, salvas em config.json)
  2. casas legislativas: tabela reaproveitada ou URLs testadas de novo
  3. para cada casa, várias ao mesmo tempo (`paralelo` no config.json):
     busca das palavras (páginas gravadas na hora), links das matérias sem
     repetição, raspagem de cada matéria (API do SAPL ou página HTML) e, se
     pedido, download dos textos originais
  4. lista de links `<nome>_links_totais.csv`, na ordem da tabela de casas
  5. tabela final `<nome>_resultado_final.csv` (a mesma de uma casa por vez)
  6. resumo

Cada etapa registra o progresso em `<nome>_estado.csv`; "Retomar um projeto"
continua de onde parou e tenta de novo o que falhou.

No modo "atualizar", as matérias de um `_resultado_final.csv` existente são
raspadas de novo, com saída em arquivos `_ATUALIZADO_<data>`.
"""

import errno
import sys
import time
import traceback
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field
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
    ETAPA_PDF,
    Linha,
)
from sapyl.downloads import baixar_da_casa, preencher_downloads
from sapyl.estado import ArquivoCSV, Cache, Estado
from sapyl.interface import ajuda, status
from sapyl.interface.entrada import (
    abrir_ou_criar,
    escolher_entrada_autoria,
    escolher_projeto,
    rotulo_do_projeto,
)
from sapyl.interface.perguntas import (
    Atalho,
    Leitor,
    Opcao,
    Perguntas,
    PerguntasMenu,
    criar_perguntas,
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
from sapyl.padroes import EntradaInvalida
from sapyl.palavras import descrever, importar_palavras, ler_palavras, preparar_termos
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
PERGUNTA_MODO = 'O que você quer fazer?'
OPCOES_MODO = [
    Opcao('Novo projeto', 'novo'),
    Opcao('Retomar um projeto', 'retomar'),
    Opcao('Atualizar um projeto', 'atualizar'),
    Opcao('Autoria e tramitação', 'autoria'),
    Opcao('Ajuda', 'ajuda'),
    Opcao('Sair', 'sair'),
]
PERGUNTA_ESTADOS = 'Em quais estados buscar?'
ATALHOS_ESTADOS = [
    Atalho('Todos os estados', 'todos', ()),
    Atalho('Sul e Sudeste', 'sul-sudeste', tuple(cl.ESTADOS_SUL_SUDESTE)),
]
PERGUNTA_QUANTAS = 'Quantas casas?'
PERGUNTA_RELEVANTES = 'Atualizar só as matérias marcadas como relevantes (coluna Relevante)?'
PERGUNTA_DOWNLOAD = (
    'Baixar os textos originais (PDFs)? Cerca de 10 MB por matéria; uma execução '
    'completa pode passar de 100 GB.'
)
COMECAR, MUDAR, CANCELAR = 'comecar', 'mudar', 'cancelar'
OPCOES_CONFIRMAR_NOVO = [
    Opcao('Começar', COMECAR),
    Opcao('Mudar respostas', MUDAR),
    Opcao('Cancelar', CANCELAR),
]
CONTINUAR = 'continuar'
OPCOES_CONTINUAR = [Opcao('Continuar', CONTINUAR), Opcao('Cancelar', CANCELAR)]
MENSAGEM_CANCELADO = 'Cancelado. Nada foi feito.'
# Horários das requisições recentes de cada site, compartilhados entre
# execuções e projetos (veja cliente_http). Fica na pasta de trabalho.
ARQUIVO_HISTORICO = '.sapl_historico.json'

MENSAGEM_CONFIG_INVALIDA = (
    '\nConfiguração inválida em {erro}\n'
    'Corrija o arquivo e rode de novo. Na chave "paralelo", apagá-la volta aos valores padrão.'
)


@dataclass
class Contexto:
    """O que a mensagem de interrupção precisa saber: o modo e o projeto (ou a entrada)."""

    modo: str | None = None
    nome: str | None = None
    cancelado: bool = False
    tela: status.Tela = field(default_factory=status.Tela)
    # resultado final da execução e o projeto dele (para oferecer a autoria, FR-21a)
    resultado: tuple[Path, gp.Projeto] | None = None


def como_retomar(modo: str | None, nome: str) -> str:
    """`rode o sapyl, escolha "Retomar um projeto" e depois "<nome>"` (conforme o modo)."""
    if modo == 'autoria':
        return f'rode o sapyl, escolha "Autoria e tramitação" e de novo "{nome}"'
    if modo == 'atualizar':
        return f'rode o sapyl no mesmo dia, escolha "Atualizar um projeto" e depois "{nome}"'
    return f'rode o sapyl, escolha "Retomar um projeto" e depois "{nome}"'


def mensagem_interrompido(contexto: Contexto) -> str:
    """O que fazer para continuar, com o caminho no menu (FR-17)."""
    if contexto.nome is None:
        return '\nInterrompido. Nada foi iniciado.'
    return (
        '\nExecução interrompida. Para continuar de onde parou, '
        f'{como_retomar(contexto.modo, contexto.nome)}.'
    )


log = registro.logger()


def _pasta_csv(raiz: str | Path) -> Path:
    return Path(raiz) / 'arquivos_csv'


def estados_da_config(config: dict[str, Any]) -> list[str]:
    """Estados do projeto: `estados` (lista vazia = todos), ou o `sul_sudeste` antigo."""
    if 'estados' in config:
        return list(config['estados'] or [])
    return list(cl.ESTADOS_SUL_SUDESTE) if config.get('sul_sudeste') else []


def texto_das_palavras(palavras: Sequence[str]) -> str:
    """Lista numerada das buscas em palavras (nunca na sintaxe do SAPL)."""
    linhas = [f'Palavras-chave ({len(palavras)} busca{"s" if len(palavras) != 1 else ""}):']
    linhas += [f'  {i}. {descrever(p)}' for i, p in enumerate(palavras, start=1)]
    return '\n'.join(linhas)


def _numero(n: int) -> str:
    return f'{n:,}'.replace(',', '.')


@dataclass
class Respostas:
    """Respostas das perguntas de um projeto novo (antes de confirmar)."""

    reusar_tabela: bool
    estados: list[str]
    limite: str
    downloads: bool
    casas: int  # quantas casas entram (no ar, se a tabela é reaproveitada)


def perguntar_configuracao(
    raiz: str | Path, perguntas: Perguntas, planilha: pd.DataFrame
) -> Respostas:
    """Lista de casas, estados, quantas casas e PDFs (FR-6 a FR-9)."""
    tabela_global = _pasta_csv(raiz) / 'casas_resultado.csv'
    testadas = None
    reusar = False
    if tabela_global.exists():
        testadas = cl.ler_tabela_casas(tabela_global, _pasta_csv(raiz) / 'casas_legislativas.xlsx')
        data = datetime.fromtimestamp(tabela_global.stat().st_mtime).strftime('%d/%m/%Y')
        no_ar = int(testadas['ativa'].sum())
        reusar = (
            perguntas.escolher(
                'Lista de casas legislativas',
                [
                    Opcao(
                        f'Usar a lista já testada (de {data}, {_numero(no_ar)} casas no ar)', 's'
                    ),
                    Opcao('Testar os sites de novo (pode levar até ~15 min)', 'n'),
                ],
            )
            == 's'
        )
    base = testadas[testadas['ativa']] if reusar and testadas is not None else planilha
    opcoes_ufs = [Opcao(uf, uf) for uf in cl.ufs(base)]
    estados = perguntas.marcar(PERGUNTA_ESTADOS, opcoes_ufs, ATALHOS_ESTADOS)
    if len(estados) == len(opcoes_ufs):
        estados = []  # todos marcados = todos
    total = len(cl.filtrar_estados(base, estados))
    limite = perguntas.escolher(
        PERGUNTA_QUANTAS,
        [
            Opcao(f'Todas as casas dos estados escolhidos ({_numero(total)})', cl.LIMITE_TODAS),
            Opcao(
                f'Teste com {cl.CASAS_NO_TESTE} casas (bom para conferir as palavras)',
                cl.LIMITE_TESTE,
            ),
        ],
    )
    casas = total if limite == cl.LIMITE_TODAS else min(total, cl.CASAS_NO_TESTE)
    downloads = perguntas.sim_nao(PERGUNTA_DOWNLOAD)
    return Respostas(reusar, estados, limite, downloads, casas)


def texto_de_confirmacao(
    projeto: gp.Projeto, palavras: Sequence[str], r: Respostas, paralelo: dict[str, int]
) -> str:
    """Resumo do projeto novo antes de começar (FR-15)."""
    if r.reusar_tabela:
        casas = f'{_numero(r.casas)} no ar (lista já testada)'
        buscas = _numero(r.casas * len(palavras))
    else:
        casas = f'{_numero(r.casas)} (o programa testa quais estão no ar antes de buscar)'
        buscas = f'até {_numero(r.casas * len(palavras))}'
    if r.limite == cl.LIMITE_TESTE:
        casas += ', teste'
    return '\n'.join(
        [
            '',
            f'Projeto: {projeto.nome} (pasta {projeto.pasta.name}/)',
            'Estados: ' + (', '.join(r.estados) if r.estados else 'todos'),
            f'Casas: {casas}',
            texto_das_palavras(palavras),
            f'Buscas: {buscas} (casas × palavras)',
            'PDFs: ' + ('sim (cerca de 10 MB por matéria)' if r.downloads else 'não'),
            f'Casas ao mesmo tempo: {paralelo["casas_ao_mesmo_tempo"]}',
            '',
        ]
    )


def configuracao_nova(palavras: list[str], r: Respostas) -> dict[str, Any]:
    """O dict salvo em config.json de um projeto novo."""
    return {
        'palavras': palavras,
        'reusar_tabela': r.reusar_tabela,
        'estados': r.estados,
        'limite': r.limite,
        'downloads': r.downloads,
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
    cliente: ClienteSAPL,
    paralelo: dict[str, int],
    progresso: Callable[[], str] | None = None,
    anunciar: bool = True,
    ao_terminar: Callable[[str], str] | None = None,
) -> padroes.Mapear:
    """`mapear(tarefa, casas)` que roda até `casas_ao_mesmo_tempo` casas ao mesmo tempo.

    Com `anunciar`, cada casa tem uma linha no começo e outra no fim (o teste
    das casas não anuncia: seriam duas linhas por casa da lista).
    """

    def mapear(tarefa: Callable[[str], Any], casas: Sequence[str]) -> list[Any]:
        return execucao.por_casa(
            casas,
            tarefa,
            paralelo['casas_ao_mesmo_tempo'],
            cliente.parar,
            progresso,
            anunciar=anunciar,
            ao_terminar=ao_terminar,
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
    estados = estados_da_config(config)
    casas = cl.limitar_casas(cl.filtrar_estados(casas, estados), config['limite'])
    if not testadas:
        log.info('Testando %d casas legislativas', len(casas))
        casas = cl.testar_casas(casas, cliente, mapear)
        # A tabela geral só é trocada quando todas as casas foram testadas
        if not estados and config['limite'] == cl.LIMITE_TODAS:
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


def contagens_do_projeto(estado: Estado, buscas: bool = True, downloads: bool = False) -> str:
    """Contagens do projeto todo (do estado), para o progresso: buscas, matérias, PDFs."""
    partes = []
    if buscas:
        partes.append(f'buscas: {estado.contagens(ETAPA_BUSCA).get("completa", 0)} completas')
    partes.append(progresso_das_materias(estado))
    if downloads:
        pdfs = estado.contagens(ETAPA_PDF)
        partes.append(f'PDFs: {pdfs.get("ok", 0)} baixados, {pdfs.get("erro", 0)} com erro')
    return '; '.join(partes)


def executar_projeto(
    projeto: gp.Projeto,
    config: dict[str, Any],
    cliente: ClienteSAPL,
    raiz: str | Path,
    tela: status.Tela | None = None,
) -> str:
    """Executa (ou retoma) um projeto do começo ao fim. Devolve o texto do resumo.

    Cada casa faz busca, links, matérias e downloads, várias casas ao mesmo
    tempo. A lista de links e a tabela final saem na ordem da tabela de casas,
    iguais às de uma casa por vez.
    """
    paralelo = ler_paralelo(projeto, config)
    inicio = preparar_cliente(cliente, paralelo)
    estado = Estado(projeto.estado)
    tela = tela or status.Tela()

    def contagens() -> str:
        return contagens_do_projeto(estado, downloads=config['downloads'])

    with ExitStack() as pilha:
        pilha.callback(estado.fechar)
        andamento = pilha.enter_context(tela.acompanhar(contagens))
        teste = mapeador(cliente, paralelo, andamento.progresso, anunciar=False)
        casas = preparar_casas(projeto, config, cliente, raiz, teste)
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
        andamento.comecar(len(fila))
        mapear = mapeador(
            cliente, paralelo, andamento.progresso, ao_terminar=andamento.resumo_da_casa
        )
        try:
            mapear(pipeline, fila)
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
            como_retomar=como_retomar('retomar', projeto.nome),
        )


def executar_atualizacao(
    raiz: str | Path,
    cliente: ClienteSAPL,
    perguntas: Perguntas,
    hoje: str | None = None,
    contexto: Contexto | None = None,
) -> str | None:
    """Modo atualização: raspa de novo as matérias de um resultado final existente.

    As colunas acrescentadas à mão no resultado (ex.: `Relevante`, anotações)
    passam para o arquivo novo. Se houver a coluna `Relevante`, pergunta se é
    para atualizar só as matérias marcadas. Devolve o resumo, ou None se a
    pessoa voltou ao menu ou cancelou (`contexto.nome` diz qual dos dois).
    """
    contexto = contexto or Contexto('atualizar')
    base = escolher_projeto(raiz, perguntas, 'Qual projeto atualizar?', so_com_resultado=True)
    if base is None:
        return None
    paralelo = ler_paralelo(base)
    tabela = ler_final(base.final)
    so_relevantes = COLUNA_RELEVANTE in tabela.columns and perguntas.sim_nao(PERGUNTA_RELEVANTES)
    downloads = perguntas.sim_nao(PERGUNTA_DOWNLOAD)
    hoje = hoje or datetime.now().strftime('%d_%m_%Y')
    projeto = gp.Projeto(raiz, base.nome, data=hoje)
    n = len(filtrar_relevantes(tabela)) if so_relevantes else len(tabela)
    perguntas.mostrar(
        '\n'.join(
            [
                '',
                f'Projeto: {rotulo_do_projeto(base)}',
                f'Matérias a atualizar: {_numero(n)}'
                + (' (só as relevantes)' if so_relevantes else ''),
                'PDFs: ' + ('sim' if downloads else 'não'),
                f'Resultado: {projeto.final.name}',
                '',
            ]
        )
    )
    contexto.nome = base.nome
    if perguntas.escolher('Começar a atualização?', OPCOES_CONTINUAR) == CANCELAR:
        contexto.cancelado = True
        return None
    inicio = preparar_cliente(cliente, paralelo)
    registro.configurar(
        projeto.pasta, projeto.nome, 'atualizacao', terminal=contexto.tela.terminal()
    )
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

        def contagens() -> str:
            return contagens_do_projeto(estado, buscas=False, downloads=downloads)

        with contexto.tela.acompanhar(contagens) as andamento:
            andamento.comecar(len(fila))
            mapear = mapeador(
                cliente, paralelo, andamento.progresso, ao_terminar=andamento.resumo_da_casa
            )
            try:
                mapear(lambda casa: raspagem.da_casa(grupos[host(casa)]), fila)
            finally:
                raspagem.fechar()
        final = montar_final(projeto.materias, links)
        if downloads:
            final = preencher_downloads(final, estado, str(projeto.downloads))
        salvar_final(juntar_colunas_extras(final, tabela), projeto.final)
        contexto.resultado = (projeto.final, base)
        return registro.resumo(
            estado,
            links,
            projeto.final,
            downloads=downloads,
            execucao=sobre_a_execucao(cliente, paralelo, inicio),
            como_retomar=como_retomar('atualizar', base.nome),
        )
    finally:
        estado.fechar()


def _linhas_do_csv(caminho: Path) -> int:
    try:
        return len(pd.read_csv(caminho, usecols=COLUNAS_ORIGEM[:1], dtype=str))
    except (ValueError, OSError):
        return 0


def executar_autoria(
    raiz: str | Path,
    cliente: ClienteSAPL,
    perguntas: Perguntas,
    contexto: Contexto | None = None,
    entrada: tuple[Path, gp.Projeto | None] | None = None,
) -> str | None:
    """Autoria e tramitação de um projeto (o resultado mais recente) ou de um CSV.

    Saída, estado e log ficam ao lado da planilha de entrada (na pasta do
    projeto, para um projeto). Com `entrada` (planilha, projeto), não pergunta
    nada: é a oferta do fim de uma execução, já aceita. Devolve o texto do
    resumo, ou None se a pessoa voltou ao menu ou cancelou.
    """
    contexto = contexto or Contexto('autoria')
    escolha = entrada or escolher_entrada_autoria(raiz, perguntas)
    if escolha is None:
        return None
    planilha, projeto = escolha
    paralelo = ler_paralelo(projeto)
    contexto.nome = projeto.nome if projeto is not None else str(planilha)
    if entrada is None:
        origem = rotulo_do_projeto(projeto) if projeto is not None else str(planilha)
        n = _numero(_linhas_do_csv(planilha))
        perguntas.mostrar(
            '\n'.join(
                [
                    '',
                    f'Entrada: {origem}',
                    f'Planilha: {planilha.name} ({n} matérias)',
                    'Cerca de 2 requisições por matéria.',
                    '',
                ]
            )
        )
        if perguntas.escolher('Começar?', OPCOES_CONTINUAR) == CANCELAR:
            contexto.cancelado = True
            return None
    inicio = preparar_cliente(cliente, paralelo)
    if projeto is not None:
        registro.configurar(
            projeto.pasta, projeto.nome, 'autoria', terminal=contexto.tela.terminal()
        )
        casas = cl.ler_tabela_casas(projeto.casas) if projeto.casas.exists() else None
        finais = cl.enderecos_finais(casas) if casas is not None else {}
        fontes = Fontes(Cache(projeto.cache), finais)
    else:
        registro.configurar(
            planilha.parent, planilha.stem, 'autoria', terminal=contexto.tela.terminal()
        )
        fontes = Fontes()
    log.info('Autoria e tramitação de %s', planilha)
    with contexto.tela.acompanhar() as andamento:
        mapear = mapeador(
            cliente, paralelo, andamento.progresso, ao_terminar=andamento.resumo_da_casa
        )
        saida, contagens = autoria.processar(planilha, cliente, fontes, mapear)
    return registro.resumo_autoria(
        contagens,
        saida,
        execucao=sobre_a_execucao(cliente, paralelo, inicio),
        como_retomar=como_retomar('autoria', contexto.nome),
    )


def _executar_e_resumir(
    projeto: gp.Projeto,
    config: dict[str, Any],
    cliente: ClienteSAPL,
    raiz: str | Path,
    contexto: Contexto,
) -> str:
    log.info('Buscando os termos: %s', '; '.join(descrever(p) for p in config['palavras']))
    texto = executar_projeto(projeto, config, cliente, raiz, contexto.tela)
    contexto.resultado = (projeto.final, projeto)
    return texto


def fluxo_novo(
    raiz: str | Path, cliente: ClienteSAPL, perguntas: Perguntas, contexto: Contexto
) -> str | None:
    """Projeto novo: confere as entradas, pergunta, confirma e executa (FR-6 a FR-15).

    Nada é criado em disco antes de "Começar". Um nome que já existe pode ser
    retomado. Devolve o resumo, ou None se a pessoa cancelou.
    """
    pasta = _pasta_csv(raiz)
    palavras = preparar_termos(ler_palavras(pasta))
    planilha = cl.importar_casas(pasta / 'casas_legislativas.xlsx')
    perguntas.mostrar('\n' + texto_das_palavras(palavras) + '\n')
    projeto, novo = abrir_ou_criar(raiz, perguntas)
    if not novo and gp.carregar_config(projeto) is not None:
        return fluxo_retomar(raiz, cliente, perguntas, contexto, projeto)
    paralelo = padroes.padroes_paralelo()
    while True:
        respostas = perguntar_configuracao(raiz, perguntas, planilha)
        perguntas.mostrar(texto_de_confirmacao(projeto, palavras, respostas, paralelo))
        escolha = perguntas.escolher('Tudo certo?', OPCOES_CONFIRMAR_NOVO)
        if escolha == COMECAR:
            break
        if escolha == CANCELAR:
            contexto.cancelado = True
            return None
    projeto.criar()
    contexto.nome = projeto.nome
    registro.configurar(
        projeto.pasta,
        projeto.nome,
        'novo' if novo else 'retomada',
        terminal=contexto.tela.terminal(),
    )
    config = configuracao_nova(palavras, respostas)
    gp.salvar_config(projeto, config)
    return _executar_e_resumir(projeto, config, cliente, raiz, contexto)


def fluxo_retomar(
    raiz: str | Path,
    cliente: ClienteSAPL,
    perguntas: Perguntas,
    contexto: Contexto,
    projeto: gp.Projeto | None = None,
) -> str | None:
    """Retoma um projeto da lista (ou o dado). Devolve o resumo, ou None (menu/cancelar).

    O resumo de confirmação vem antes de qualquer mensagem sobre a execução, e
    o `paralelo` é conferido antes dele (FR-14, FR-16).
    """
    if projeto is None:
        projeto = escolher_projeto(raiz, perguntas, 'Qual projeto retomar?')
        if projeto is None:
            return None
    config = gp.carregar_config(projeto)
    if config is None:
        # projeto de versão antiga, sem config.json: as perguntas de um projeto novo
        perguntas.mostrar(f'O projeto "{projeto.nome}" não tem config.json; responda de novo.')
        pasta = _pasta_csv(raiz)
        palavras = preparar_termos(ler_palavras(pasta))
        planilha = cl.importar_casas(pasta / 'casas_legislativas.xlsx')
        perguntas.mostrar(texto_das_palavras(palavras))
        respostas = perguntar_configuracao(raiz, perguntas, planilha)
        config = configuracao_nova(palavras, respostas)
    paralelo = ler_paralelo(projeto, config)
    perguntas.mostrar(
        '\n'.join(
            [
                '',
                f'Projeto: {rotulo_do_projeto(projeto)}',
                texto_das_palavras(config['palavras']),
                'PDFs: ' + ('sim' if config['downloads'] else 'não'),
                f'Casas ao mesmo tempo: {paralelo["casas_ao_mesmo_tempo"]}',
                '',
            ]
        )
    )
    contexto.nome = projeto.nome
    if perguntas.escolher('Continuar este projeto?', OPCOES_CONTINUAR) == CANCELAR:
        contexto.cancelado = True
        return None
    if not projeto.config.exists():
        gp.salvar_config(projeto, config)
    registro.configurar(projeto.pasta, projeto.nome, 'retomada', terminal=contexto.tela.terminal())
    log.info('Retomando o projeto %s', projeto.nome)
    avisar_palavras_mudadas(raiz, config['palavras'])
    return _executar_e_resumir(projeto, config, cliente, raiz, contexto)


PERGUNTA_AUTORIA = (
    'Buscar agora a autoria e a tramitação das {n} matérias do resultado? '
    'Cerca de 2 requisições por matéria.'
)


def oferecer_autoria(
    raiz: Path, cliente: ClienteSAPL, perguntas: Perguntas, feito: Contexto, atual: list[Contexto]
) -> None:
    """Depois de um resultado final, oferece a autoria e tramitação dele (FR-21a).

    Não pergunta nada se a execução foi a própria autoria ou se o resultado
    não tem matérias. `atual[0]` passa a ser o contexto da autoria (para a
    mensagem de interrupção).
    """
    if feito.modo == 'autoria' or feito.resultado is None:
        return
    final, projeto = feito.resultado
    n = _linhas_do_csv(final)
    if not n or not perguntas.sim_nao(PERGUNTA_AUTORIA.format(n=_numero(n)), padrao=False):
        return
    atual[0] = Contexto('autoria', tela=feito.tela)
    texto = executar_autoria(raiz, cliente, perguntas, atual[0], entrada=(final, projeto))
    if texto is not None:
        feito.tela.resumo(texto)


def _menu(
    raiz: Path, cliente: ClienteSAPL, perguntas: Perguntas, tela: status.Tela, atual: list
) -> int:
    fluxos = {
        'novo': fluxo_novo,
        'retomar': fluxo_retomar,
        'atualizar': lambda r, c, p, ctx: executar_atualizacao(r, c, p, contexto=ctx),
        'autoria': lambda r, c, p, ctx: executar_autoria(r, c, p, contexto=ctx),
    }
    while True:
        modo = perguntas.escolher(PERGUNTA_MODO, OPCOES_MODO)
        if modo == 'sair':
            return 0
        if modo == 'ajuda':
            perguntas.mostrar(ajuda.TEXTO)
            continue
        contexto = atual[0] = Contexto(modo, tela=tela)
        texto = fluxos[modo](raiz, cliente, perguntas, contexto)
        if texto is not None:
            tela.resumo(texto)
            oferecer_autoria(raiz, cliente, perguntas, contexto, atual)
            return 0
        if contexto.cancelado:
            perguntas.mostrar(MENSAGEM_CANCELADO)
            return 0


def _erro_inesperado(erro: Exception, raiz: Path, log_antes: str | None) -> str:
    """Grava o traceback (no log desta execução, ou num arquivo novo) e devolve a mensagem."""
    caminho = registro.log_atual()
    if caminho is not None and caminho != log_antes:
        log.debug('Erro inesperado', exc_info=erro)  # DEBUG: só no arquivo
    else:
        agora = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        caminho = str(raiz / f'sapyl_erro_{agora}.log')
        detalhes = ''.join(traceback.format_exception(type(erro), erro, erro.__traceback__))
        Path(caminho).write_text(f'{registro.NOME} {__version__}\n{detalhes}', encoding='utf-8')
    return (
        f'\nErro inesperado: {type(erro).__name__}: {erro}\n'
        f'Os detalhes estão em {caminho}. O que já foi feito está salvo; se for um '
        'projeto, ele pode ser retomado. Se o erro se repetir, abra um aviso em '
        'https://github.com/leoaucar/sapyl/issues com esse arquivo.'
    )


def main(
    entrada: Leitor = input, cliente: ClienteSAPL | None = None, raiz: str | Path = '.'
) -> int:
    """Menu principal: projeto novo, retomar, atualizar, autoria e tramitação, ajuda, sair.

    Devolve o código de saída: 0 (também ao sair ou cancelar); 1 se a execução
    foi interrompida, se uma casa parou por um erro inesperado ou num erro
    inesperado; 2 se um arquivo de entrada, o config.json do projeto ou uma
    permissão de pasta está errado, ou se o disco encheu (FR-22).
    """
    raiz = Path(raiz)
    perguntas = criar_perguntas(entrada)
    # O servidor (IP) de cada site, para o limite por servidor (veja cliente_http)
    cliente = cliente or ClienteSAPL(
        historico=str(raiz / ARQUIVO_HISTORICO), servidor_de=resolver_servidor
    )
    print(BOAS_VINDAS)
    tela = (
        status.Tela(ao_vivo=True, console=perguntas.console)
        if isinstance(perguntas, PerguntasMenu)
        else status.Tela()
    )
    atual = [Contexto(tela=tela)]
    log_antes = registro.log_atual()
    try:
        return _menu(raiz, cliente, perguntas, tela, atual)
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C a qualquer momento, ou Ctrl+D / fim da entrada numa pergunta
        print(mensagem_interrompido(atual[0]))
        return 1
    except EntradaInvalida as erro:
        print(f'\n{erro}')
        return 2
    except padroes.ConfiguracaoInvalida as erro:
        print(MENSAGEM_CONFIG_INVALIDA.format(erro=erro))
        return 2
    except execucao.FalhaNasCasas as erro:
        # As outras casas terminaram e estão no estado; a retomada refaz só estas
        log.error(str(erro))
        print(mensagem_interrompido(atual[0]))
        return 1
    except PermissionError as erro:
        onde = erro.filename or 'um arquivo da pasta de trabalho'
        print(
            f'\nSem permissão para gravar ou ler {onde}. Confira as permissões da pasta '
            '(ou rode o sapyl numa pasta sua) e rode de novo.'
        )
        return 2
    except OSError as erro:
        if erro.errno != errno.ENOSPC:
            print(_erro_inesperado(erro, raiz, log_antes))
            return 1
        print(
            f'\nO disco encheu ao gravar {erro.filename or "os arquivos do projeto"}. '
            'Libere espaço e retome o projeto: nada do que já foi gravado se perde.'
        )
        return 2
    except Exception as erro:
        print(_erro_inesperado(erro, raiz, log_antes))
        return 1


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
