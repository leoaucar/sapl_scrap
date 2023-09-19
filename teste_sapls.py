import requests
import pandas as pd

#importar tabela
#selecionar colunas

#classe que importa tabela

#classe para testes
r = requests.get('https://sapl.santana.ap.leg.br/sistema/search/?q=educação')
#verificar se os resultados sao ok
print(r.text)