"""Download dos textos originais (PDFs) das matérias.

- Nome estável: `<host-da-casa>_<sapl_id>.<extensão>` (ex.:
  `sapl.riobranco.ac.leg.br_34049.pdf`), igual em toda execução.
- O arquivo é baixado aos pedaços para `<nome>.part` e só ganha o nome final
  quando termina; se falhar, o `.part` é apagado.
- Cada matéria é baixada no máximo uma vez; arquivos já baixados (estado
  `ok` e arquivo presente) são pulados ao retomar.
- O resultado de cada download vai para o estado (`pdf`) e para as colunas
  `arquivo_pdf` e `download_status` (`ok`, `erro` ou `sem_pdf`).

Com várias casas ao mesmo tempo, cada casa baixa os seus textos logo depois
das suas matérias (`baixar_da_casa`, que só grava o estado), e as colunas da
tabela final são preenchidas no fim a partir do estado (`preencher_downloads`).
`baixar_todos` faz as duas coisas de uma vez, para uma tabela pronta.
"""

import os
from urllib.parse import urlparse

import pandas as pd
import requests

from sapyl import registro
from sapyl.cliente_http import ClienteSAPL
from sapyl.colunas import ETAPA_PDF, Linha
from sapyl.estado import Estado

TAMANHO_PEDACO = 64 * 1024
TIMEOUT_DOWNLOAD = (10, 60)
EXTENSOES = ('.pdf', '.doc', '.docx', '.odt', '.rtf', '.txt', '.html', '.zip')

log = registro.logger('download')


def nome_arquivo(chave: str, link: str) -> str:
    """`sapl.x.leg.br/123` + link do texto -> `sapl.x.leg.br_123.pdf`."""
    extensao = os.path.splitext(urlparse(link).path)[1].lower()
    if extensao not in EXTENSOES:
        extensao = '.pdf'
    return chave.replace('/', '_') + extensao


def baixar_arquivo(link: str, destino: str, cliente: ClienteSAPL) -> str:
    """Baixa `link` para `destino`. Devolve '' se deu certo, ou o motivo da falha."""
    parcial = destino + '.part'
    resposta = cliente.get(link, stream=True, timeout=TIMEOUT_DOWNLOAD)
    if not resposta.ok:
        return resposta.erro
    try:
        with open(parcial, 'wb') as arquivo:
            for pedaco in resposta.iter_content(TAMANHO_PEDACO):
                cliente.verificar_parada()  # Ctrl+C não espera o arquivo inteiro
                if pedaco:
                    arquivo.write(pedaco)
        os.replace(parcial, destino)
        return ''
    except (requests.RequestException, OSError) as erro:
        log.warning('Download interrompido de %s: %s', link, erro)
        return 'download interrompido'
    finally:
        resposta.fechar()
        if os.path.exists(parcial):
            os.remove(parcial)


def _chave(linha: Linha) -> str:
    return f'{urlparse(linha["Link Casa"]).hostname}/{linha["sapl_id"]}'


def baixar_da_casa(linhas: list[Linha], pasta: str, cliente: ClienteSAPL, estado: Estado) -> None:
    """Baixa os textos das matérias `ok` de `linhas` e grava cada resultado no estado.

    `linhas`: matérias raspadas (com `Link Casa`, `sapl_id`, `status` e
    `texto_original`). Arquivos já baixados (estado `ok` e arquivo presente)
    são pulados.
    """
    os.makedirs(pasta, exist_ok=True)
    a_baixar = [linha for linha in linhas if linha['status'] == 'ok']
    if a_baixar:
        registro.andamento(
            log, registro.PDFS, 0, len(a_baixar), 'Downloads: %d matérias', len(a_baixar)
        )
    for n, linha in enumerate(a_baixar, start=1):
        chave = _chave(linha)
        link = linha['texto_original']
        if not link:
            if estado.status(ETAPA_PDF, chave) != 'sem_pdf':
                estado.registrar(ETAPA_PDF, chave, 'sem_pdf')
            continue
        nome = nome_arquivo(chave, link)
        destino = os.path.join(pasta, nome)
        if estado.status(ETAPA_PDF, chave) == 'ok' and os.path.exists(destino):
            continue
        erro = baixar_arquivo(link, destino, cliente)
        estado.registrar(ETAPA_PDF, chave, 'erro' if erro else 'ok', erro)
        registro.andamento(
            log,
            registro.PDFS,
            n,
            len(a_baixar),
            'Download %d de %d (%s): %s',
            n,
            len(a_baixar),
            chave,
            erro or nome,
            status='erro' if erro else 'ok',
        )


def preencher_downloads(final: pd.DataFrame, estado: Estado, pasta: str) -> pd.DataFrame:
    """Preenche `arquivo_pdf` e `download_status` das matérias `ok` a partir do estado.

    `ok` só com o arquivo na pasta; `sem_pdf` sem texto original; `erro` se o
    último download falhou; vazio se nunca foi tentado (execução interrompida).
    """
    final = final.copy()
    for i in final.index[final['status'] == 'ok']:
        chave = _chave(final.loc[i])
        link = final.at[i, 'texto_original']
        arquivo, situacao = '', ''
        if not link:
            situacao = 'sem_pdf'
        else:
            nome = nome_arquivo(chave, link)
            status = estado.status(ETAPA_PDF, chave)
            if status == 'ok' and os.path.exists(os.path.join(pasta, nome)):
                arquivo, situacao = nome, 'ok'
            elif status == 'erro':
                situacao = 'erro'
        final.at[i, 'arquivo_pdf'], final.at[i, 'download_status'] = arquivo, situacao
    return final


def baixar_todos(
    final: pd.DataFrame, pasta: str, cliente: ClienteSAPL, estado: Estado
) -> pd.DataFrame:
    """Baixa os textos das matérias `ok` da tabela final e preenche as colunas de download."""
    baixar_da_casa(final.to_dict('records'), pasta, cliente, estado)
    return preencher_downloads(final, estado, pasta)
