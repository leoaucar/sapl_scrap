import pandas as pd

def tratamento_resultados(tabela_resultados, atualizar):
    df = pd.read_csv(tabela_resultados, index_col=0, dtype=str)
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
                            '11':'Tipo de Materia Legislativa',
                            '12':'texto_original',
                            '13':'texto_integral'})
    #df = df.drop(['IndiceOLD'], axis=1)
    df['Ano'] = df['Ano'].str.replace('Ano\n\n', '')
    df['Ementa'] = df['Ementa'].str.replace('Ementa\n\n', '')
    #df['Data'] = df['Data'].str.replace('Data\n\n', '')
    df['Numero'] = df['Numero'].str.replace('Número\n\n', '')
    df['Observacao'] = df['Observacao'].str.replace('Observação', '')
    df['Observacao'] = df['Observacao'].str.replace('\n\n', '')
    df['Tipo de Materia Legislativa'] = df['Tipo de Materia Legislativa'].str.replace('Tipo de Matéria Legislativa\n\n', '')
    if atualizar == False:
        df['texto_original'] = df['Link Casa'] + df['texto_original'].str.replace('Texto Original\n\n', '')
    elif atualizar == True:
        df['texto_original'] = df['texto_original'].str.replace('Texto Original\n\n', '')
    #df['texto_integral'] = df['texto_integral'].str.replace('')
    df = df.replace(r'\r',' ', regex=True)
    return df