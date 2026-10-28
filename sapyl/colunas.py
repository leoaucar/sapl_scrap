"""Nomes de colunas dos arquivos do projeto e das etapas do estado.

Única fonte dessas listas: os outros módulos importam daqui e não repetem
nenhuma delas (conferido por tests/test_colunas.py).
"""

# Uma linha de qualquer um destes arquivos (coluna -> valor)
Linha = dict[str, str]

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

# Páginas da busca (`<nome>_paginas_busca.csv`): só os links de matérias de
# cada página, separados por espaço
COLUNAS_PAGINAS = ['Casa', 'Palavra', 'Pagina', 'links', 'link']

# Arquivo bruto da busca das versões até 0.1 (`<nome>_resultados_crus_casas.csv`,
# com o HTML de cada página). Só é lido, para retomar projetos antigos.
COLUNAS_CRU = ['Indice', 'Casa', 'Palavra', 'Pagina', 'html', 'link']

# Tabela de casas testadas (`casas_resultado.csv`). `url_final`: endereço para onde
# o site da casa redireciona (vazio se não redireciona)
COLUNAS_CASAS = ['url', 'ativa', 'motivo', 'uf', 'url_final']

# Arquivo de estado (`<nome>_estado.csv`) e suas etapas
CAMPOS_ESTADO = ['etapa', 'chave', 'status', 'erro', 'quando']
ETAPA_BUSCA = 'busca'
ETAPA_MATERIA = 'materia'
ETAPA_PDF = 'pdf'
ETAPAS = (ETAPA_BUSCA, ETAPA_MATERIA, ETAPA_PDF)
