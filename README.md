# sapl_scrap

[![testes](https://github.com/leoaucar/sapl_scrap/actions/workflows/tests.yml/badge.svg)](https://github.com/leoaucar/sapl_scrap/actions/workflows/tests.yml)

Raspador de matérias legislativas em Câmaras Municipais e Assembleias que usam o
**SAPL** (Sistema de Apoio ao Processo Legislativo, do Interlegis).

O programa pesquisa uma lista de palavras-chave na busca de cada casa legislativa,
coleta os links das matérias encontradas, obtém os dados de cada matéria (título,
ementa, data, tipo, situação, link do texto original…) e gera uma planilha final
em CSV. Opcionalmente, baixa os textos originais (PDFs).

O que ele garante:

- **Nenhuma matéria vazia em silêncio.** Toda linha tem `status` (`ok` ou
  `erro`) e, quando falha, o motivo na coluna `erro`.
- **Respeito aos servidores.** No máximo 35 requisições por minuto em cada
  site (o limite do SAPL); quando o site pede para esperar (`HTTP 429`), o
  programa espera e tenta de novo.
- **Retomada.** Se a execução parar no meio (Ctrl+C, queda de energia ou de
  internet), basta rodar de novo e escolher "retomar": o que já foi feito não
  é refeito, e o que falhou é tentado outra vez.
- **Sem duplicatas.** Uma matéria encontrada por várias palavras aparece uma
  vez só, com todas as palavras na coluna `Palavras`.

Uma execução completa é demorada justamente por respeitar o limite de cada
site: uma casa com 1 000 matérias leva cerca de 30 minutos. Veja estimativas
e próximos passos no [ROADMAP](ROADMAP.md).

## Requisitos

- Python 3.10 ou superior
- Conexão com a internet

## Instalação

```bash
git clone https://github.com/leoaucar/sapl_scrap.git
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

#### Arquivos de exemplo

`arquivos_csv/exemplo_palavras_chave.csv` mostra cada formato. Para usá-lo,
copie-o para `arquivos_csv/palavras_chave.csv`. Cada linha vira a busca:

| Linha do arquivo                 | Busca no SAPL                       | Significa                              |
|----------------------------------|-------------------------------------|----------------------------------------|
| `orçamento`                      | `"orçamento"`                       | uma palavra                            |
| `plano diretor`                  | `"plano+diretor"`                   | a expressão exata                      |
| `lei orgânica`                   | `"lei+orgânica"`                    | a expressão exata                      |
| `"orçamento, emenda impositiva"` | `"orçamento"+"emenda+impositiva"`   | os dois termos juntos na mesma matéria |
| `saneamento básico`              | `"saneamento+básico"`               | com acento                             |
| `saneamento basico`              | `"saneamento+basico"`               | a mesma ideia sem acento               |

Variantes de grafia (com e sem acento, com hífen ou espaço) vão em linhas
separadas. Cada linha é mais uma busca em cada casa, e todas contam no limite
de 35 requisições por minuto de cada site.

`arquivos_csv/exemplo_palavras_chave_educacao.csv` é uma lista real de
pesquisa (educação, gênero e ideologia), com 23 buscas por casa: um teste
maior, de cerca de uma hora para 10 casas por causa do limite.

Use o `palavras_chave.csv` (fora do git) para as suas próprias listas, em vez
de editar o `palavras_chave.xlsx`, que é o exemplo guardado no repositório.

### Casas legislativas — `arquivos_csv/casas_legislativas.xlsx`

Lista das casas que usam o SAPL. O programa usa as colunas **`UF`** e
**`URL do serviço`** (ex.: `https://sapl.cascavel.pr.leg.br/`).

## Como usar

Na raiz do projeto, com o ambiente virtual ativado:

```bash
python programa.py
```

O programa faz perguntas no terminal. Responda digitando o número da opção
(respostas inválidas são pedidas de novo):

1. **Apenas atualizar a tabela de um projeto anterior?** `1` sim
   (veja [Atualizar um projeto](#atualizar-um-projeto)), `2` não.
2. **Nome do projeto**: é criada a pasta `<nome>_proj/`. Se o nome já existe,
   o programa oferece **retomar** esse projeto ou escolher outro nome; um
   projeto existente nunca é sobrescrito.
3. **Usar a mesma tabela de casas do último projeto?** (só aparece se já existe
   `arquivos_csv/casas_resultado.csv`) `1` reaproveita a tabela, sem testar os
   sites de novo; `2` testa quais sites estão no ar.
4. **Restringir a busca a Sul e Sudeste?** `1` limita a RJ, SP, RS, SC, MG,
   ES e PR; `2` busca em todo o país.
5. **Limitar a busca para teste?** `1` todas as casas, `2` as 50 primeiras,
   `3` as 50 últimas, `4` apenas 10 casas (bom para um primeiro teste).
6. **Baixar os textos originais (PDFs)?** `1` sim, `2` não.

As respostas ficam salvas no projeto (`config.json`); ao retomar, nada é
perguntado de novo.

> Comece com a opção `4` (10 casas) para conferir se as palavras-chave estão
> boas antes de uma busca completa.

### Retomar um projeto

Rode `python programa.py`, responda `2` na primeira pergunta, digite o nome do
projeto e escolha `1- retomar este projeto`. O programa:

- não refaz as buscas que terminaram (e refaz as que ficaram incompletas);
- não raspa de novo as matérias com `status = ok`;
- tenta de novo as matérias com `status = erro`;
- não baixa de novo os PDFs que já estão na pasta.

### Resumo e log

No fim de cada execução aparece um resumo: casas pesquisadas, buscas
incompletas, matérias encontradas, únicas, raspadas e com erro, downloads e o
caminho do resultado. Se houve falhas, ele lembra de retomar o projeto.

Tudo o que aparece no terminal, e mais uma linha para cada requisição feita
aos sites, fica em `<nome>_proj/<nome>.log`.

## Resultados

Tudo fica dentro da pasta `<nome>_proj/`:

| Arquivo                               | Conteúdo                                              |
|---------------------------------------|-------------------------------------------------------|
| **`<nome>_resultado_final.csv`**      | **Planilha final, uma linha por matéria — use esta**  |
| `casas_resultado.csv`                 | Casas do projeto: `url, ativa, motivo, uf`            |
| `<nome>_resultados_crus_casas.csv`    | HTML de cada página de busca                          |
| `<nome>_links_totais.csv`             | Links únicos de matérias encontrados                  |
| `<nome>_materias_legislativas.csv`    | Cada tentativa de raspagem (a mais recente vale)      |
| `<nome>_estado.csv`                   | Progresso, usado para retomar                         |
| `<nome>.log`                          | Registro da execução                                  |
| `config.json`                         | Respostas dadas ao criar o projeto                    |
| `downloads/`                          | Textos originais, como `<site>_<id>.pdf`              |

### Colunas da planilha final

| Coluna | Conteúdo |
|---|---|
| `Link Materia`, `Link Casa` | Página da matéria e site da casa |
| `Palavras` | Todas as buscas que encontraram a matéria, separadas por `; ` |
| `Titulo`, `Ementa`, `Ano`, `Numero` | Identificação da matéria |
| `Data` | Data de apresentação (`dd/mm/aaaa`) |
| `Observacao`, `Tipo de Materia Legislativa` | Como no SAPL |
| `texto_original` | Link do texto original (PDF) |
| `Indexacao` | Palavras-chave cadastradas pela casa |
| `Em Tramitacao`, `Regime Tramitacao` | `Sim`/`Não`; Ordinária, Urgência… |
| `Materia Anexada` | Matérias às quais esta está anexada |
| `Resultado` | Resultado (aprovada, rejeitada…), quando a casa preenche |
| `Data Publicacao`, `Numero Protocolo` | Quando a casa preenche |
| `Ultima Atualizacao` | Última edição do registro no SAPL (só pela API) |
| `sapl_id` | Número da matéria no SAPL da casa |
| `fonte` | `api` (API do SAPL) ou `html` (página, em versões antigas do SAPL) |
| `status`, `erro` | `ok`, ou `erro` com o motivo (`HTTP 429`, `timeout`…) |
| `raspada_em` | Data e hora da raspagem |
| `arquivo_pdf`, `download_status` | Nome do arquivo baixado; `ok`, `erro` ou `sem_pdf` |

As colunas `Assuntos` e `texto_integral` das versões anteriores saíram: elas
não existem mais nas páginas do SAPL e vinham sempre vazias.

## Atualizar um projeto

Para atualizar os dados de matérias já encontradas (por exemplo, depois de
filtrar manualmente as relevantes no `_resultado_final.csv`):

1. Rode `python programa.py`.
2. Responda `1` na pergunta "Deseja apenas atualizar a tabela…".
3. Digite o nome do projeto (com ou sem `_proj`).

O resultado é salvo como `<nome>_resultado_final_ATUALIZADO_<dd_mm_aaaa>.csv`
e os downloads, se pedidos, em `downloads<dd_mm_aaaa>/`. A atualização também
pode ser retomada no mesmo dia.

## Autoria e tramitação

O módulo `sapyl/autoria.py` acrescenta as colunas `Autoria` e `Tramite` (a
tramitação mais recente) a uma planilha de resultados.

1. Copie o CSV de resultados (com a coluna `Link Materia`) para a pasta onde
   você roda o programa (a raiz do repositório).
2. Rode, dessa pasta, e escolha o arquivo na lista:

   ```bash
   python -m sapyl.autoria
   ```

O arquivo escolhido não é alterado; o resultado vai para
`<nome>_autoria_tramitacao.csv`, com as colunas `status_autoria`,
`status_tramitacao` e `erro_autoria_tramitacao`.

## Testes

Os testes rodam sem internet, com páginas reais do SAPL salvas em
`tests/fixtures/` (veja o [README das fixtures](tests/fixtures/README.md)).

```bash
pip install -r requirements-dev.txt
pytest                                   # todos os testes, com cobertura
pytest tests/test_cliente_http.py -k 429    # só alguns
```

Eles também rodam no GitHub Actions a cada push, em Python 3.10 e 3.12.

## Estrutura do código

O código fica no pacote `sapyl/`. `programa.py`, na raiz, é só um atalho.

| Arquivo                 | Função                                                        |
|-------------------------|---------------------------------------------------------------|
| `sapyl/interface/principal.py` | Comando `sapyl`; etapas: novo/retomar/atualizar        |
| `sapyl/interface/entrada.py`   | Perguntas com validação, escolha do projeto            |
| `sapyl/colunas.py`      | Nomes das colunas e das etapas (lista única)                  |
| `sapyl/cliente_http.py` | Cliente HTTP único: limite por site, 429, retentativas, log   |
| `sapyl/casas.py`        | Lista de casas, teste dos sites, UF, filtros                  |
| `sapyl/palavras.py`     | Lê e formata as palavras-chave para a busca                   |
| `sapyl/busca.py`        | Busca página a página em cada casa                            |
| `sapyl/links.py`        | Links de matérias: chave, duplicatas, páginas de busca        |
| `sapyl/materias/`       | Dados de cada matéria: API (`api.py`) ou HTML (`html.py`)     |
| `sapyl/tabela.py`       | Monta a planilha final                                        |
| `sapyl/downloads.py`    | Baixa os textos originais                                     |
| `sapyl/estado.py`       | Progresso em disco, para retomar                              |
| `sapyl/projeto.py`      | Pasta e arquivos do projeto                                   |
| `sapyl/registro.py`     | Log e resumo final                                            |
| `sapyl/autoria.py`      | Autoria e tramitação                                          |

O desenvolvimento segue specs em [`specs/`](specs/) (constituição, stack e uma
pasta por mudança).

## Licença

Copyright (C) 2023–2026 Leonardo Nogueira Aucar. Concepção e revisão: Renata
Aquino e Fernanda Moura. Veja [AUTHORS.md](AUTHORS.md).

Este programa é software livre: você pode usá-lo, estudá-lo, modificá-lo e
redistribuí-lo nos termos da **GNU Affero General Public License, versão 3**
(veja [LICENSE](LICENSE)). Versões modificadas, inclusive as oferecidas como
serviço pela rede, devem continuar livres sob a mesma licença.

Termo adicional (seção 7, alínea b, da AGPL-3.0): cópias e versões modificadas
devem preservar o aviso de copyright e os créditos de autoria de
[AUTHORS.md](AUTHORS.md).

Se você usar o programa ou os dados produzidos com ele em pesquisas ou
publicações, pedimos que o cite como indicado em [AUTHORS.md](AUTHORS.md).
