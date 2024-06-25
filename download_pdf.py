import requests
import shutil

def download_arquivo(link, id,path):
    url = link
    id = str(id)
    try:
        response = requests.get(url)
        url = str(url)
        with open(id+'.pdf', mode="wb") as file:
            file.write(response.content)
        shutil.move('./'+id+'.pdf',path+'/'+id+'.pdf')
    except:
        pass
    