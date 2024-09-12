from bs4 import BeautifulSoup
import os
import glob
import pandas as pd
import requests


path = os.getcwd() 
csv_files = glob.glob(os.path.join(path, "*final.csv"))
dados = pd.read_csv(csv_files[0], index_col=0)
dados['Autoria'] = ""
dados['Tramite'] = ""


def buscar_autoria(link):
    url = link + '/autoria'
    try:
        response = requests.get(url, timeout=3)

        soup = BeautifulSoup(response.text, features='html.parser')
        for a in soup.find_all('tr'):
            autorias_totais = a
    except:
        autorias_totais = ''
        pass
    return autorias_totais

def buscar_tramitacao(link):
    url = link + '/tramitacao'
    tramites_totais = []
    try:
        response = requests.get(url, timeout=3)
        soup = BeautifulSoup(response.text, features='html.parser')
        for a in soup.find_all('tr'):
            tramites_totais = a
    except:
        tramites_totais = ''
        pass
    return tramites_totais

tramites_totais = []
autorias_totais = []
for i in dados['Link Materia'][15:25]:
    autorias_totais.append(buscar_autoria(i))
    tramites_totais.append(buscar_tramitacao(i))

#print(autorias_totais)
print(tramites_totais)