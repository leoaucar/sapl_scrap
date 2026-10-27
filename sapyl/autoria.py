"""Acrescenta as colunas Autoria e Tramite a uma planilha de resultados.

Uso (de dentro da pasta com o CSV):
    python -m sapyl.autoria
O programa lista os CSVs da pasta e pergunta qual usar. O arquivo escolhido
não é alterado: o resultado vai para `<nome>_autoria_tramitacao.csv`.

- `Autoria`: autores da matéria, separados por '; ' (ex.: "PEDRO LONGO (Parlamentar)").
- `Tramite`: última tramitação, "<data> | <unidade local> | <unidade destino> | <status>".
- `status_autoria`, `status_tramitacao`: `ok` ou `erro`; `erro` traz o motivo.

As requisições passam pelo mesmo cliente do raspador (limite de 35 por
minuto por site, retentativas em 429/5xx).
"""
from pathlib import Path
import re
import sys

from bs4 import BeautifulSoup
import pandas as pd

from sapyl.interface.entrada import perguntar_opcao
from sapyl.cliente_http import ClienteSAPL
from sapyl import registro

SUFIXO_SAIDA = '_autoria_tramitacao'
log = registro.logger('autoria')


def link_base(link):
    """Link da matéria sem `/ta` nem barra final."""
    return re.sub(r'/ta/?$', '', str(link).strip()).rstrip('/')


def ler_tabela(html):
    """Linhas da primeira tabela da página, como dicts {cabeçalho: texto}."""
    tabela = BeautifulSoup(html, 'html.parser').find('table')
    if tabela is None:
        return []
    cabecalhos = [th.get_text(' ', strip=True) for th in tabela.find_all('th')]
    linhas = []
    for tr in tabela.find_all('tr'):
        celulas = [' '.join(td.get_text(' ').split()) for td in tr.find_all('td')]
        if celulas:
            linhas.append(dict(zip(cabecalhos, celulas)))
    return linhas


def buscar_autoria(link, cliente):
    """(texto, erro). Texto: 'AUTOR (Descrição); ...'."""
    resposta = cliente.get(link_base(link) + '/autoria')
    if not resposta.ok:
        return '', resposta.erro
    autores = []
    for linha in ler_tabela(resposta.texto):
        autor = linha.get('Autor', '')
        descricao = linha.get('Descrição', '')
        if autor:
            autores.append(f'{autor} ({descricao})' if descricao else autor)
    return '; '.join(autores), ''


def buscar_tramitacao(link, cliente):
    """(texto, erro). Texto da tramitação mais recente (a primeira da tabela)."""
    resposta = cliente.get(link_base(link) + '/tramitacao')
    if not resposta.ok:
        return '', resposta.erro
    linhas = ler_tabela(resposta.texto)
    if not linhas:
        return '', ''
    ultima = linhas[0]
    campos = ['Data Tramitação', 'Unidade Local', 'Unidade Destino', 'Status']
    return ' | '.join(ultima.get(c, '') for c in campos), ''


def escolher_csv(pasta, entrada=input):
    """Lista os CSVs da pasta (menos as saídas deste script) e pergunta qual usar."""
    arquivos = sorted(p for p in Path(pasta).glob('*.csv') if not p.stem.endswith(SUFIXO_SAIDA))
    if not arquivos:
        return None
    menu = ''.join(f'{i}- {p.name}\n' for i, p in enumerate(arquivos, start=1))
    escolha = perguntar_opcao('Qual arquivo usar?\n' + menu,
                              [str(i) for i in range(1, len(arquivos) + 1)], entrada)
    return arquivos[int(escolha) - 1]


def processar(caminho, cliente):
    """Lê o CSV, busca autoria e tramitação de cada matéria e grava o novo arquivo."""
    dados = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    dados = dados.drop(columns=[c for c in dados.columns if c.startswith('Unnamed')])
    autorias, tramites, st_aut, st_tram, erros = [], [], [], [], []
    for i, link in enumerate(dados['Link Materia'], start=1):
        log.info('Autoria e tramitação %d de %d: %s', i, len(dados), link)
        autoria, erro_a = buscar_autoria(link, cliente)
        tramite, erro_t = buscar_tramitacao(link, cliente)
        autorias.append(autoria)
        tramites.append(tramite)
        st_aut.append('erro' if erro_a else 'ok')
        st_tram.append('erro' if erro_t else 'ok')
        erros.append('; '.join(e for e in (erro_a and f'autoria: {erro_a}',
                                           erro_t and f'tramitação: {erro_t}') if e))
    dados['Autoria'], dados['Tramite'] = autorias, tramites
    dados['status_autoria'], dados['status_tramitacao'] = st_aut, st_tram
    dados['erro_autoria_tramitacao'] = erros
    saida = Path(caminho).with_name(Path(caminho).stem + SUFIXO_SAIDA + '.csv')
    dados.to_csv(saida, index=False)
    falhas = sum(1 for e in erros if e)
    log.info('Pronto: %s (%d matérias, %d com falha)', saida, len(dados), falhas)
    return saida


def main(pasta='.', entrada=input, cliente=None):
    registro.configurar(pasta, 'autoria_tramitacao')
    try:
        caminho = escolher_csv(pasta, entrada)
    except (KeyboardInterrupt, EOFError):
        print('\nInterrompido.')
        return 1
    if caminho is None:
        print('Nenhum arquivo .csv nesta pasta. Copie para cá o resultado final de um projeto.')
        return 1
    try:
        # mesmo arquivo do programa principal quando roda na mesma pasta
        historico = Path(pasta) / '.sapl_historico.json'
        processar(caminho, cliente or ClienteSAPL(historico=str(historico)))
    except KeyboardInterrupt:
        print('\nInterrompido. O arquivo de entrada não foi alterado.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
