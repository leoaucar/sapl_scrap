"""Download dos PDFs dos textos originais das matérias."""
import requests
import shutil


def download_arquivo(link, id, path):
    """Baixa `link` como `<id>.pdf` e move o arquivo para a pasta `path`.

    Qualquer erro (link vazio, falha de rede...) é ignorado silenciosamente.
    """
    url = link
    id = str(id)
    try:
        response = requests.get(url)
        # Grava primeiro na pasta atual e depois move para o destino
        with open(id+'.pdf', mode="wb") as file:
            file.write(response.content)
        shutil.move('./'+id+'.pdf', path+'/'+id+'.pdf')
    except:
        pass
