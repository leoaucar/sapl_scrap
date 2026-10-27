"""Download dos textos originais (PDFs) das matérias.

- Nome estável: `<host-da-casa>_<sapl_id>.<extensão>` (ex.:
  `sapl.riobranco.ac.leg.br_34049.pdf`), igual em toda execução.
- O arquivo é baixado aos pedaços para `<nome>.part` e só ganha o nome final
  quando termina; se falhar, o `.part` é apagado.
- Cada matéria é baixada no máximo uma vez; arquivos já baixados (estado
  `ok` e arquivo presente) são pulados ao retomar.
- O resultado de cada download vai para o estado (`pdf`) e para as colunas
  `arquivo_pdf` e `download_status` (`ok`, `erro` ou `sem_pdf`).
"""
import os
from urllib.parse import urlparse

import requests

from sapyl import registro

TAMANHO_PEDACO = 64 * 1024
TIMEOUT_DOWNLOAD = (10, 60)
EXTENSOES = ('.pdf', '.doc', '.docx', '.odt', '.rtf', '.txt', '.html', '.zip')

log = registro.logger('download')


def nome_arquivo(chave, link):
    """`sapl.x.leg.br/123` + link do texto -> `sapl.x.leg.br_123.pdf`."""
    extensao = os.path.splitext(urlparse(link).path)[1].lower()
    if extensao not in EXTENSOES:
        extensao = '.pdf'
    return chave.replace('/', '_') + extensao


def baixar_arquivo(link, destino, cliente):
    """Baixa `link` para `destino`. Devolve '' se deu certo, ou o motivo da falha."""
    parcial = destino + '.part'
    resposta = cliente.get(link, stream=True, timeout=TIMEOUT_DOWNLOAD)
    if not resposta.ok:
        return resposta.erro
    try:
        with open(parcial, 'wb') as arquivo:
            for pedaco in resposta.iter_content(TAMANHO_PEDACO):
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


def baixar_todos(final, pasta, cliente, estado):
    """Baixa os textos das matérias `ok` da tabela final e preenche as colunas de download."""
    os.makedirs(pasta, exist_ok=True)
    final = final.copy()
    a_baixar = final.index[final['status'] == 'ok']
    log.info('Downloads: %d matérias', len(a_baixar))
    for n, i in enumerate(a_baixar, start=1):
        chave = f"{urlparse(final.at[i, 'Link Casa']).hostname}/{final.at[i, 'sapl_id']}"
        link = final.at[i, 'texto_original']
        if not link:
            final.at[i, 'arquivo_pdf'], final.at[i, 'download_status'] = '', 'sem_pdf'
            if estado.status('pdf', chave) != 'sem_pdf':
                estado.registrar('pdf', chave, 'sem_pdf')
            continue
        nome = nome_arquivo(chave, link)
        destino = os.path.join(pasta, nome)
        if estado.status('pdf', chave) == 'ok' and os.path.exists(destino):
            final.at[i, 'arquivo_pdf'], final.at[i, 'download_status'] = nome, 'ok'
            continue
        erro = baixar_arquivo(link, destino, cliente)
        if erro:
            final.at[i, 'arquivo_pdf'], final.at[i, 'download_status'] = '', 'erro'
            estado.registrar('pdf', chave, 'erro', erro)
        else:
            final.at[i, 'arquivo_pdf'], final.at[i, 'download_status'] = nome, 'ok'
            estado.registrar('pdf', chave, 'ok')
        log.info('Download %d de %d (%s): %s', n, len(a_baixar), chave, erro or nome)
    return final
