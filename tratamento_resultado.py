import pandas as pd

def tratamento_resultados(tabela_resultados):
    df = pd.read_csv(tabela_resultados, index_col=0)
    df = df.rename(columns={'0':'IndiceOLD',
                            '1':'Link Materia',
                            '2':'Link Casa',
                            '3':'Palavras',
                            '4':'Titulo',
                            '5':'Ementa',
                            '6':'Ano',
                            '7':'Data',
                            '8':'Numero',
                            '9':'Observacao',
                            '10':'Assuntos',
                            '11':'Tipo de Materia Legislativa',})
    df = df.drop(['IndiceOLD'], axis=1)
    df['Ano'] = df['Ano'].str.replace('Ano\n\n', '')
    df['Ementa'] = df['Ementa'].str.replace('Ementa\n\n', '')
    #df['Data'] = df['Data'].str.replace('Data\n\n', '')
    df['Numero'] = df['Numero'].str.replace('Número\n\n', '')
    df['Observacao'] = df['Observacao'].str.replace('Observação', '')
    df['Observacao'] = df['Observacao'].str.replace('\n\n', '')
    df['Tipo de Materia Legislativa'] = df['Tipo de Materia Legislativa'].str.replace('Tipo de Matéria Legislativa\n\n', '')
    df = df.replace(r'\r',' ', regex=True)
    return df