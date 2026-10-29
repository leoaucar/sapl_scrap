# SAPyL

**Raspador do Sistema de Apoio Legislativo**

Acompanhe, num só lugar, o que está tramitando em dezenas de câmaras e
assembleias brasileiras que usam o SAPL. Software livre (AGPL-3.0).

[![testes](https://github.com/leoaucar/sapyl/actions/workflows/tests.yml/badge.svg)](https://github.com/leoaucar/sapyl/actions/workflows/tests.yml)

Página do projeto, com instalação e uso passo a passo:
<https://leoaucar.github.io/sapyl/>

## Como citar

Se você usar o SAPyL, ou dados produzidos com ele, em trabalhos ou
publicações, cite assim:

> AUCAR, Leonardo Nogueira; AQUINO, Renata; MOURA, Fernanda. *SAPyL: Raspador do
> Sistema de Apoio Legislativo*. 2023–2026. Software livre (AGPL-3.0).

Versões anteriores a 0.2 se chamavam *sapl_scrap*. Veja também
[AUTHORS.md](AUTHORS.md).

## Para que serve

Muitas Câmaras Municipais e Assembleias Legislativas publicam seus projetos
de lei, requerimentos e outras matérias no **SAPL** (Sistema de Apoio ao
Processo Legislativo, do Interlegis). Cada casa tem o seu site, e não há uma
busca que junte todas. O SAPyL faz essa busca por você: é feito para
pesquisadoras e pesquisadores, jornalistas, organizações da sociedade civil e
qualquer pessoa que queira saber o que está sendo proposto sobre um tema em
muitas casas legislativas ao mesmo tempo.

O programa pesquisa uma lista de palavras-chave na busca de cada casa legislativa,
coleta os links das matérias encontradas, obtém os dados de cada matéria (título,
ementa, data, tipo, situação, link do texto original…) e gera uma planilha final
em CSV. Opcionalmente, baixa os textos originais (PDFs).

O que ele garante:

- **Nenhuma matéria vazia em silêncio.** Toda linha tem `status` (`ok` ou
  `erro`) e, quando falha, o motivo na coluna `erro`.
- **Respeito aos servidores.** No máximo 35 requisições por minuto em cada
  site (o limite do SAPL), e no máximo 120 por minuto somando todas as casas
  que ficam no mesmo servidor; quando o site pede para esperar (`HTTP 429`), o
  programa espera e tenta de novo.
- **Várias casas ao mesmo tempo.** Até 8 casas são processadas em paralelo,
  com o mesmo resultado de uma casa por vez.
- **Retomada.** Se a execução parar no meio (Ctrl+C, queda de energia ou de
  internet), basta rodar de novo e escolher "retomar": o que já foi feito não
  é refeito, e o que falhou é tentado outra vez.
- **Sem duplicatas.** Uma matéria encontrada por várias palavras aparece uma
  vez só, com todas as palavras na coluna `Palavras`.

Uma execução completa é demorada justamente por respeitar os limites: uma
casa com 1 000 matérias leva cerca de 30 minutos, e as casas que ficam no
mesmo servidor dividem o limite dele (veja
[Várias casas ao mesmo tempo](#várias-casas-ao-mesmo-tempo)). Veja
estimativas e próximos passos no [ROADMAP](ROADMAP.md).

## Requisitos

- Python 3.10 ou superior
- Conexão com a internet

## Instalação

```bash
git clone https://github.com/leoaucar/sapyl.git
cd sapyl

python3 -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate

pip install .
```

> O repositório se chamava `sapl_scrap`; os endereços antigos redirecionam
> para o novo. Quem já tem uma cópia pode atualizar o endereço com
> `git remote set-url origin https://github.com/leoaucar/sapyl.git`.

Isso instala o comando `sapyl` no ambiente virtual (confira com
`sapyl --version`). Quem já usava `pip install -r requirements.txt` pode
continuar: o arquivo agora só instala o programa.

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
sapyl
```

(ou `python -m sapyl`, ou ainda `python programa.py` na raiz do repositório)

O programa faz perguntas no terminal. Responda digitando o número da opção
(respostas inválidas são pedidas de novo):

1. **O que você quer fazer?** `1` novo projeto ou retomar um projeto, `2`
   atualizar um projeto (veja [Atualizar um projeto](#atualizar-um-projeto)),
   `3` autoria e tramitação (veja [Autoria e tramitação](#autoria-e-tramitação)).
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

Rode `sapyl`, escolha `1` na primeira pergunta, digite o nome do
projeto e escolha `1- retomar este projeto`. O programa:

- não refaz as buscas que terminaram (e refaz as que ficaram incompletas);
- não raspa de novo as matérias com `status = ok`;
- tenta de novo as matérias com `status = erro`;
- não baixa de novo os PDFs que já estão na pasta.

A retomada usa as palavras-chave salvas no projeto (`config.json`). Se o
arquivo de palavras mudou desde então, o programa avisa quais palavras são
novas e quais saíram, e continua com as salvas. Para buscar palavras novas,
crie um projeto novo.

### Várias casas ao mesmo tempo

O limite de 35 requisições por minuto é **por site**, então o programa ganha
tempo processando várias casas em paralelo, nunca acelerando uma casa. Cada
casa faz, em sequência, as suas buscas, os links, as matérias e (se pedido)
os PDFs; as casas pequenas terminam cedo e não esperam as grandes. O teste
dos sites, o modo atualização e a autoria e tramitação também rodam assim.
A planilha final sai igual à de uma casa por vez (na ordem da tabela de
casas).

Quase todas as casas ficam no **mesmo servidor** do Interlegis (o mesmo
endereço IP). Por isso, além do limite de cada site, há um limite por
servidor: no máximo 120 requisições por minuto, somando todas as casas dele.
Se casas diferentes do mesmo servidor começam a receber `HTTP 429`, o
programa avisa no log e reduz esse limite pela metade até o fim da execução
(nunca abaixo de 35). Nada se perde: as requisições esperam e são feitas de
novo.

Os valores ficam no `config.json` do projeto, na chave `paralelo`:

```json
"paralelo": {"casas_ao_mesmo_tempo": 8, "limite_por_servidor": 120}
```

Só mude se tiver um motivo (por exemplo, um aviso do Interlegis). Para mudar,
edite o arquivo antes de retomar o projeto. `casas_ao_mesmo_tempo` tem de ser
um número inteiro de pelo menos 1 (com 1, uma casa por vez), e
`limite_por_servidor` de pelo menos 35. Um valor inválido para o programa
antes de qualquer requisição, com uma mensagem dizendo o que corrigir.
Projetos criados por versões anteriores não têm essa chave e usam os valores
padrão.

Com Ctrl+C, todas as casas param em poucos segundos (no máximo o tempo de uma
requisição em andamento), e a retomada continua de onde parou.

### Resumo e log

No fim de cada execução aparece um resumo: casas pesquisadas, buscas
incompletas, matérias encontradas, únicas, raspadas e com erro, downloads, o
tempo da execução, o limite usado em cada servidor (e se foi reduzido) e o
caminho do resultado. Se houve falhas, ele lembra de retomar o projeto. A
última linha mostra o log desta execução.

Durante a execução, cada linha começa com a casa a que se refere
(`[sapl.x.leg.br] Matéria 3 de 120: …`), e a cada minuto aparece uma linha
de progresso geral (casas concluídas, em andamento e na fila; matérias
raspadas e com erro).

Cada execução (novo projeto, retomada, atualização) tem o seu próprio log em
`<nome>_proj/logs/<nome>_<aaaa-mm-dd_hhmmss>_<modo>.log`, com tudo o que
aparece no terminal e mais uma linha para cada requisição feita aos sites.
Projetos criados antes da versão 0.2 também têm um `<nome>.log`, que fica
como estava.

Se o site de uma casa redireciona para outro domínio, o teste das casas grava
o endereço novo em `url_final` (na tabela de casas) e todas as requisições
vão direto para ele. A casa continua identificada pelo endereço original:
`Link Casa`, `Link Materia` e as chaves não mudam.

## Resultados

Tudo fica dentro da pasta `<nome>_proj/`:

| Arquivo                               | Conteúdo                                              |
|---------------------------------------|-------------------------------------------------------|
| **`<nome>_resultado_final.csv`**      | **Planilha final, uma linha por matéria — use esta**  |
| `casas_resultado.csv`                 | Casas: `url, ativa, motivo, uf, url_final`            |
| `<nome>_paginas_busca.csv`            | Links de matérias de cada página de busca             |
| `<nome>_links_totais.csv`             | Links únicos de matérias encontrados                  |
| `<nome>_materias_legislativas.csv`    | Cada tentativa de raspagem (a mais recente vale)      |
| `<nome>_estado.csv`                   | Progresso, usado para retomar                         |
| `logs/`                               | Um log por execução (`<nome>_<data_hora>_<modo>.log`) |
| `config.json`                         | Respostas dadas ao criar o projeto                    |
| `cache.json`                          | Fonte de cada casa (API/HTML) e nomes já consultados  |
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

1. Rode `sapyl`.
2. Escolha `2` (atualizar um projeto).
3. Digite o nome do projeto (com ou sem `_proj`).

O resultado é salvo como `<nome>_resultado_final_ATUALIZADO_<dd_mm_aaaa>.csv`
e os downloads, se pedidos, em `downloads<dd_mm_aaaa>/`. A atualização também
pode ser retomada no mesmo dia.

Colunas que você acrescentou à planilha (anotações, classificações…) passam
para o arquivo atualizado, depois das colunas do programa, na linha da mesma
matéria.

Se a planilha tiver uma coluna **`Relevante`**, o programa pergunta se é para
atualizar só as matérias marcadas. Contam como marcadas: `sim`, `s`, `x`, `1`
ou `true` (maiúsculas e espaços não importam). As demais ficam de fora do
arquivo atualizado e dos downloads.

## Autoria e tramitação

A opção `3` do menu acrescenta a uma planilha as colunas `Autoria` (os autores
da matéria) e `Tramite` (a tramitação mais recente: data, unidade local,
unidade de destino e status).

1. Rode `sapyl` e escolha `3`.
2. Digite o **nome de um projeto** (usa o resultado final mais recente dele,
   inclusive um `_ATUALIZADO_`) ou o **caminho de um CSV** qualquer com a
   coluna `Link Materia`.

A planilha de entrada não é alterada. O resultado vai para
`<entrada>_autoria_tramitacao.csv`, ao lado dela, com as colunas
`status_autoria`, `status_tramitacao`, `erro_autoria_tramitacao` e
`fonte_autoria` (`api` ou `html`). Os dados vêm da API do SAPL, ou das páginas
da matéria nas casas sem API; as duas fontes dão o mesmo texto.

Se a execução parar no meio, rode de novo, escolha `3` e digite a mesma
entrada: só o que falta (ou falhou) é buscado de novo.

## Testes

Os testes rodam sem internet, com páginas reais do SAPL salvas em
`tests/fixtures/` (veja o [README das fixtures](tests/fixtures/README.md)).

```bash
pip install -e ".[dev]"                  # o programa em modo editável, mais pytest e ruff
pytest                                   # todos os testes, com cobertura
pytest tests/test_cliente_http.py -k 429 # só alguns
ruff check . && ruff format --check .    # estilo e formatação
```

Eles também rodam no GitHub Actions a cada push, em Python 3.10 e 3.12, junto
com uma instalação limpa (`pip install .` e `sapyl --version`).

## Estrutura do código

O código fica no pacote `sapyl/`. `programa.py`, na raiz, é só um atalho.

| Arquivo                 | Função                                                        |
|-------------------------|---------------------------------------------------------------|
| `sapyl/interface/principal.py` | Comando `sapyl`; etapas: novo/retomar/atualizar        |
| `sapyl/interface/entrada.py`   | Perguntas com validação, escolha do projeto            |
| `sapyl/colunas.py`      | Nomes das colunas e das etapas (lista única)                  |
| `sapyl/padroes.py`      | Limites e valores padrão; confere o `paralelo` do config.json |
| `sapyl/cliente_http.py` | Cliente HTTP único: limite por site e por servidor, 429, retentativas, log |
| `sapyl/execucao.py`     | Várias casas ao mesmo tempo (threads), Ctrl+C e progresso     |
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
