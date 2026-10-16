"""Acrescenta as colunas Autoria e Tramite a uma planilha de resultados.

Uso (de dentro desta pasta, com um único .csv nela):
    python autoria_e_tramit.py
O CSV é sobrescrito com as novas colunas.
"""
from bs4 import BeautifulSoup
import os
import glob
import pandas as pd
import requests


def buscar_autoria(link):
    """Texto das duas primeiras células da página <materia>/autoria ('' em caso de erro)."""
    url = link + '/autoria'
    autorias_totais = []
    try:
        response = requests.get(url, timeout=3)

        soup = BeautifulSoup(response.text, features='html.parser')
        for a in soup.find_all('td')[0:2]:
            a = a.get_text().replace('\n','').strip()
            autorias_totais.append(a)
    except:
        autorias_totais = ''
        pass
    autorias_totais = ' '.join(autorias_totais)
    return autorias_totais

def buscar_tramitacao(link):
    """Lista com as quatro primeiras células (último trâmite) da página <materia>/tramitacao."""
    url = link + '/tramitacao'
    tramites_totais = []
    try:
        response = requests.get(url, timeout=3)
        soup = BeautifulSoup(response.text, features='html.parser')
        for a in soup.find_all('td')[0:4]:
            a = a.get_text().replace('\n','').strip()
            tramites_totais.append(a)
    except:
        tramites_totais = ''
    return tramites_totais

if __name__ == '__main__':
    path = os.getcwd() 
    # Usa o primeiro CSV encontrado na pasta atual
    csv_files = glob.glob(os.path.join(path, "*.csv"))
    dados = pd.read_csv(csv_files[0], index_col=0)
    dados['Autoria'] = ""
    dados['Tramite'] = ""

    tramites_totais = []

    
    autorias_totais = []
    for i in dados['Link Materia']:
        print("raspando autoria e tramitaçao de: " + str(i))
        autorias_totais.append(buscar_autoria(i))
        tramites_totais.append(buscar_tramitacao(i))

    dados['Autoria'] = autorias_totais
    dados['Tramite'] = tramites_totais
    file_name = os.path.basename(csv_files[0])

    dados.to_csv(file_name)