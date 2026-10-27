"""Nomes de colunas dos arquivos do projeto e das etapas do estado.

Única fonte dessas listas: os outros módulos importam daqui e não repetem
nenhuma delas (conferido por tests/test_colunas.py).
"""

# Separador de valores múltiplos numa célula (palavras, autores, anexadas)
SEPARADOR = '; '

# Colunas que dizem de onde veio cada matéria
COLUNAS_ORIGEM = ['Link Materia', 'Link Casa', 'Palavras']

# Dados da matéria, na ordem do resultado final. As 11 primeiras são as da
# versão anterior (sem `Assuntos` e `texto_integral`, que não existem mais no SAPL).
COLUNAS_DADOS = [
    'Titulo',
    'Ementa',
    'Ano',
    'Data',
    'Numero',
    'Observacao',
    'Tipo de Materia Legislativa',
    'texto_original',
    'Indexacao',
    'Em Tramitacao',
    'Regime Tramitacao',
    'Materia Anexada',
    'Resultado',
    'Data Publicacao',
    'Numero Protocolo',
    'Ultima Atualizacao',
]

# Resultado final (`<nome>_resultado_final.csv`), na ordem
COLUNAS_FINAIS = (
    COLUNAS_ORIGEM
    + COLUNAS_DADOS
    + ['sapl_id', 'fonte', 'status', 'erro', 'raspada_em', 'arquivo_pdf', 'download_status']
)

# Matérias raspadas (`<nome>_materias_legislativas.csv`): também a chave
COLUNAS_MATERIAS = ['chave'] + COLUNAS_FINAIS

# Links únicos (`<nome>_links_totais.csv`)
COLUNAS_LINKS = ['chave'] + COLUNAS_ORIGEM + ['sapl_id']

# Arquivo bruto da busca (`<nome>_resultados_crus_casas.csv`)
COLUNAS_CRU = ['Indice', 'Casa', 'Palavra', 'Pagina', 'html', 'link']

# Tabela de casas testadas (`casas_resultado.csv`)
COLUNAS_CASAS = ['url', 'ativa', 'motivo', 'uf']

# Arquivo de estado (`<nome>_estado.csv`) e suas etapas
CAMPOS_ESTADO = ['etapa', 'chave', 'status', 'erro', 'quando']
ETAPA_BUSCA = 'busca'
ETAPA_MATERIA = 'materia'
ETAPA_PDF = 'pdf'
ETAPAS = (ETAPA_BUSCA, ETAPA_MATERIA, ETAPA_PDF)
