from raspador import raspar_materia_legislativa
import pandas as pd
resultados = raspar_materia_legislativa('./arquivos_csv/links_achados.csv')
df = pd.DataFrame(resultados)
df.to_csv('./arquivos_csv/conteudos_materias.csv')