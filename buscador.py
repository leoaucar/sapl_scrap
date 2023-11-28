import requests
from palavras_chave import importar_palavras
from casas_legislativas import importar_casas, teste_url_ativa
from raspador import raspar_resultados
from gerenciador_projetos import montar_tabela

lista_casas = importar_casas()
#print(lista_casas)

#validacao das casas legislativas online
casas_resultado = teste_url_ativa(lista_casas[0:20]) #limitado 20 para teste
print(casas_resultado)

#validacao das palavras chave
palavras = importar_palavras()
print(palavras)

#menu inicial e escolhas

#em novo projeto
#cria pasta do projeto
#carrega as palavras chave
#carrega as casas legislativas
#testa as casas legislativas
#raspa as casas legislativas

#em projeto ja executado
#atualiza as casas legislativas
#testa casas legislativas
#atualiza lista de palavras
#atualiza resultados