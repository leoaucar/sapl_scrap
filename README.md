# sapl_scrap

Raspador de matérias legislativas em Câmaras Municipais e Assembleias que usam o
**SAPL** (Sistema de Apoio ao Processo Legislativo, do Interlegis).

O programa pesquisa uma lista de palavras-chave na busca de cada casa legislativa,
coleta os links das matérias encontradas, raspa os dados de cada matéria (título,
ementa, ano, número, tipo, links dos textos) e gera uma planilha final em CSV.
Opcionalmente, baixa os PDFs dos textos originais.

> **Atenção (problema conhecido):** os servidores do SAPL limitam cada site a
> 35 requisições por minuto. Acima disso, a versão atual grava as matérias
> bloqueadas como linhas vazias, sem avisar. Confira a coluna `Titulo` do
> resultado final. Veja o [ROADMAP](ROADMAP.md) para detalhes, estimativas de
> tempo e próximos passos.

## Requisitos

- Python 3.10 ou superior
- Conexão com a internet

## Instalação

```bash
git clone <url-do-repositorio>
cd sapl_scrap

python3 -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Preparando os arquivos de entrada

Os arquivos de entrada ficam na pasta `arquivos_csv/`.

### Palavras-chave — `arquivos_csv/palavras_chave.xlsx`

Planilha com uma coluna chamada **`Palavras`**. Cada linha é uma busca.

| Palavras                      |
|-------------------------------|
| linguagem neutra              |
| lingua portuguesa, norma culta |

- Termos com espaço viram uma expressão exata (`"linguagem+neutra"`).
- Termos separados por vírgula na mesma linha são buscados juntos
  (`"lingua+portuguesa"+"norma+culta"`).

Se existir um `arquivos_csv/palavras_chave.csv` com a mesma coluna, ele tem
prioridade sobre o `.xlsx`.

### Casas legislativas — `arquivos_csv/casas_legislativas.xlsx`

Lista das casas que usam o SAPL. O programa usa as colunas **`UF`** e
**`URL do serviço`** (ex.: `https://sapl.cascavel.pr.leg.br/`).

## Como usar

Na raiz do projeto, com o ambiente virtual ativado:

```bash
python programa.py
```

O programa faz perguntas no terminal. Responda digitando o número da opção:

1. **Usar a mesma tabela de casas do último projeto?**
   - `1` (sim): reaproveita `arquivos_csv/casas_resultado.csv`, sem testar as
     casas de novo (mais rápido).
   - `2` (não): testa novamente quais sites das casas estão no ar.
2. **Apenas atualizar a tabela de um projeto anterior?**
   - `1` (sim): pede o nome de um projeto existente e raspa de novo as matérias
     do seu `_resultado_final.csv` (veja [Atualizar um projeto](#atualizar-um-projeto)).
   - `2` (não): cria um projeto novo.
3. **Nome do projeto**: é criada a pasta `<nome>_proj/`. O nome não pode
   repetir o de uma pasta já existente.
4. **Restringir a busca a Sul e Sudeste?** `1` limita a RJ, SP, RS, SC, MG,
   ES e PR; `2` busca em todo o país.
5. **Limitar a busca para teste?**
   - `1` todas as casas
   - `2` as 50 primeiras
   - `3` as 50 últimas
   - `4` apenas 10 casas (bom para um primeiro teste)
6. **Realizar downloads?** `1` baixa os PDFs dos textos originais das matérias.

> A busca completa em todas as casas pode levar várias horas. Comece com a
> opção `4` (10 casas) para conferir se as palavras-chave estão boas.

## Resultados

Tudo fica dentro da pasta `<nome>_proj/`:

| Arquivo                               | Conteúdo                                         |
|---------------------------------------|--------------------------------------------------|
| `casas_resultado.csv`                 | Casas testadas e se o site respondeu             |
| `<nome>_resultados_crus_casas.csv`    | HTML bruto de cada página de busca               |
| `<nome>_links_totais.csv`             | Links de matérias encontrados                    |
| `<nome>_materias_legislativas.csv`    | Dados raspados de cada matéria, sem tratamento   |
| **`<nome>_resultado_final.csv`**      | **Planilha final, limpa — use esta**             |
| `downloads/`                          | PDFs dos textos originais (se escolhido)         |

Colunas da planilha final: `Link Materia`, `Link Casa`, `Palavras`, `Titulo`,
`Ementa`, `Ano`, `Data`, `Numero`, `Observacao`, `Assuntos`,
`Tipo de Materia Legislativa`, `texto_original`, `texto_integral`.

## Atualizar um projeto

Para atualizar os dados de matérias já encontradas (por exemplo, depois de
filtrar manualmente as relevantes no `_resultado_final.csv`):

1. Rode `python programa.py`.
2. Responda `1` na pergunta “Deseja apenas atualizar a tabela…”.
3. Digite o nome do projeto (com ou sem `_proj`).

O resultado é salvo como `<nome>_resultado_final_ATUALIZADO_<dd_mm_aaaa>.csv`
e os downloads, se pedidos, em `downloads<data>/`.

## Autoria e tramitação

O script `autoria_e_tramitacao/autoria_e_tramit.py` acrescenta as colunas
`Autoria` e `Tramite` a uma planilha de resultados.

1. Copie o CSV de resultados (com a coluna `Link Materia`) para a pasta
   `autoria_e_tramitacao/`. Deixe **apenas um** `.csv` nessa pasta, pois o
   script lê o primeiro que encontrar.
2. Rode o script de dentro da pasta:

   ```bash
   cd autoria_e_tramitacao
   python autoria_e_tramit.py
   ```

O arquivo é sobrescrito com as novas colunas.

## Estrutura do código

| Arquivo                   | Função                                                    |
|---------------------------|-----------------------------------------------------------|
| `programa.py`             | Ponto de entrada; conduz o fluxo e as perguntas           |
| `gerenciador_projetos.py` | Cria a pasta e as tabelas iniciais do projeto             |
| `palavras_chave.py`       | Lê e formata as palavras-chave para a busca               |
| `casas_legislativas.py`   | Lê a lista de casas e testa quais sites estão no ar       |
| `buscador.py`             | Faz as buscas página a página em cada casa                |
| `raspador.py`             | Extrai os links e os dados de cada matéria                |
| `tratamento_resultado.py` | Renomeia colunas e limpa os textos raspados               |
| `download_pdf.py`         | Baixa os PDFs dos textos originais                        |
| `testes.py`               | Testes manuais de raspagem e de palavras-chave            |
