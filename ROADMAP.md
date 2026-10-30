# Roadmap

Diagnóstico e plano de evolução do SAPyL (antes `sapl_scrap`), a partir da avaliação do
código e de um teste real feito em 15/10/2026.

## 1. Teste realizado

- **Palavras:** `plano diretor`, `lei orgânica`, `orçamento, emenda impositiva`
- **Casas:** as 10 primeiras da tabela (todas do Acre, incluindo a Assembleia
  Legislativa e a Câmara de Rio Branco)
- **Ambiente:** Python 3.12, pandas 3.0.6. O código funcionou sem ajustes.

| Etapa                      | Volume                          | Tempo   |
|----------------------------|---------------------------------|---------|
| Busca                      | 443 páginas de resultado        | ~2 min  |
| Raspagem das matérias      | 1306 links (1195 únicos)        | ~4 min  |
| Download de PDFs           | 151 arquivos, **1,6 GB**        | ~1 min  |
| **Total**                  |                                 | **~7 min** |

**Problema grave encontrado:** 1131 das 1306 matérias (87%) vieram **vazias**.
Os servidores do SAPL limitam a **35 requisições por minuto** por site e, depois
disso, respondem `HTTP 429 Too Many Requests` com `Retry-After: 60`. O raspador
não verifica o status da resposta e grava a página de erro como se fosse uma
matéria sem dados. Por isso só 151 PDFs foram baixados.

A busca (`/sistema/search/`) não pareceu sofrer esse limite: 392 páginas de
Rio Branco foram buscadas em ~2 min, e a paginação terminou normalmente com
404.

## 2. Estimativa de tempo de uma execução completa

A tabela tem **1 404 casas** (não ~840, como se estimava antes); numa amostra
de 60, um terço não existe mais no DNS. Os resultados se concentram nas casas
grandes (assembleias e capitais). No teste, 2 das 10 casas deram 100% das
matérias.

**Achado de 27/10/2026 (só consultas de DNS):** quase todas as casas que
funcionam ficam no **mesmo servidor** do Interlegis. As 10 casas do Acre e 37
de 60 casas sorteadas apontam para `201.54.51.178` (3 para `.179`). Por isso
o paralelismo (Fase 2) tem, além do limite de 35 por site, um limite por
servidor (120 por minuto no começo).

- **Teste das URLs** (quando a tabela é refeita): até 5 s por casa, ou seja,
  **até ~70 min**.
- **Busca:** com 3 palavras, ~840 × 3 buscas de no mínimo 1 página, mais a
  paginação das casas grandes. Ordem de grandeza: **30 min a 2 h**.
- **Raspagem das matérias** (a parte cara): com o limite de 35/min respeitado,
  cada casa leva `nº de matérias ÷ 35` minutos. Rio Branco sozinha (1126
  matérias) levaria ~32 min. Para algumas dezenas de milhares de matérias no
  total, uma execução **sequencial levaria de 10 a 20 h**.
- **Downloads:** ~10 MB por PDF em média, o que pode passar de **100 GB** numa
  execução completa.

Com a Fase 2 (até 8 casas ao mesmo tempo, 120 requisições por minuto no
servidor compartilhado), a raspagem fica cerca de **3,4 vezes mais rápida**
que uma casa por vez: algo como **3 a 6 h** para a execução completa, e o
teste das URLs cai para uns **15 min**. O limite do servidor é o que manda, não
o número de casas. Na validação (29/10/2026, 50 casas e 23 palavras), 175 por
minuto deixou a execução 19 % mais rápida sem nenhum 429, mas as respostas
mais lentas pioraram 1,55 vez; o padrão ficou em 120 (próximo valor a testar:
150, numa execução completa).

## 3. Bugs e riscos conhecidos

> **Situação:** os itens 1–9, 11 e 12 foram corrigidos na spec
> `2026-10-24-runtime-improvements`. O item 10 foi corrigido na Fase 1b
> (spec `2026-10-24-organizacao-e-pendencias`), junto com as pendências
> encontradas depois.

Em ordem de prioridade (lista original de 15/10/2026):

1. **Limite de requisições (429) ignorado** (`raspador.py`): as matérias
   bloqueadas viram linhas vazias. *Correção:* checar `status_code`, esperar o
   `Retry-After` e tentar de novo, e limitar cada casa a no máximo 35
   requisições por minuto.
2. **Retentativa infinita** (`buscador.py`): quando `requests.get` lança
   exceção, a mesma URL é tentada para sempre (`continue` sem limite).
3. **A busca para em qualquer status diferente de 200**: um 429 ou 500 na
   busca cortaria os resultados sem aviso.
4. **Campos que nunca são preenchidos:** `div_id_data`, `div_id_assuntos` e
   `div_id_texto_integral` não existem nas páginas atuais do SAPL. A data está
   em `div_id_data_apresentacao`. As colunas `Data`, `Assuntos` e
   `texto_integral` saem sempre vazias.
5. **Duplicatas:** a mesma matéria encontrada por várias palavras é raspada e
   baixada várias vezes (111 de 1306 no teste).
6. **Sem `timeout`** em `raspador.py` e `download_pdf.py`: uma conexão travada
   para o programa indefinidamente.
7. **A restrição Sul/Sudeste é ignorada** quando se reaproveita a tabela de
   casas (resposta `1` na primeira pergunta).
8. **Travamentos por entrada inválida:** `int(input(...))` na restrição e no
   download; `os.mkdir` quando o projeto ou a pasta `downloads<data>` já existe.
9. **Erros silenciosos:** casas com erro de conexão somem da lista
   (`teste_url_ativa`), e falhas de download são ignoradas (`except: pass`).
10. **Arquivo de busca bruto grande:** ~10 MB por 10 casas, ou seja, ~1 GB numa
    execução completa.
11. **Pequenos:**
    - "50 últimas casas" pega 49.
    - A opção `5` é aceita no menu de limite.
    - `BeautifulSoup` é chamado sem parser explícito.
    - `autoria_e_tramit.py` lê "o primeiro CSV" da pasta e grava a tramitação
      como lista.
12. **Não usada e quebrada:** `teste_conteudo_atualizado` compara texto com
    número.

## 4. Roadmap

### ⚠️ Prioridade máxima: falha silenciosa no limite de requisições
Resolver antes de qualquer outra coisa, porque hoje uma execução completa
**perde a maior parte dos dados sem avisar** (87% das matérias no teste).

- [x] Detectar `HTTP 429` (e outros status ≠ 200) na raspagem das matérias e
      na busca
- [x] Esperar o tempo de `Retry-After` (60 s) e tentar de novo, com número
      máximo de tentativas
- [x] Respeitar o limite de 35 requisições por minuto por casa (assim o 429
      nem chega a acontecer)
- [x] Nunca gravar a página de erro como matéria: marcar a linha com
      `status = erro` e listar as falhas no fim da execução
- [x] Testar de novo com as 10 casas do teste: 0 matérias vazias esperadas
      (24–25/10/2026: 1189 matérias, todas com dados, 0 erros)

### Fase 1: Correção e robustez
- [x] Sessão HTTP única (`requests.Session`) com `timeout` e retentativas
      respeitando `Retry-After` para 429/5xx (`http_sapl.py`)
- [x] Limitador de taxa por casa (35 req/min, configurável)
- [x] Registrar falhas em uma coluna `status` em vez de gravar linhas vazias
- [x] Corrigir os seletores (`div_id_data_apresentacao` etc.); dados pela API
      JSON do SAPL, com a página HTML como reserva
- [x] Remover duplicatas antes de raspar e de baixar
- [x] Logging (`logging`) em vez de `print`, com um arquivo de log por projeto
- [x] Retomar uma execução interrompida (pular matérias já raspadas)

> Fase 1 e "Prioridade máxima" implementadas e validadas contra os sites reais
> na spec [`specs/2026-10-24-runtime-improvements/`](specs/2026-10-24-runtime-improvements/)
> (veja `validation.md`).

### Fase 1b: Organização do código, nova identidade e pendências
Spec [`specs/2026-10-24-organizacao-e-pendencias/`](specs/2026-10-24-organizacao-e-pendencias/),
aprovada em 27/10/2026. A Fase 1 só reorganizou o necessário para testar; esta fase arruma
a estrutura antes do paralelismo e fecha os bugs que ficaram de fora.

**Organização do código**
- [x] Transformar o projeto em um pacote Python com `pyproject.toml`,
      separando camadas: HTTP, busca, matérias (API/HTML), downloads,
      estado/projeto, interface (perguntas)
- [x] Um único ponto de entrada (`python -m <pacote>`), mantendo
      `programa.py` como atalho
- [x] Trazer `autoria_e_tramitacao/` para dentro do pacote, como mais uma
      opção do programa (sem o ajuste de `sys.path`)
- [x] Nomes consistentes (funções, colunas, arquivos de saída)
- [x] Tipagem (type hints) e docstrings nas funções públicas
- [x] Formatação e lint automáticos (`ruff`) rodando também no CI
- [x] Separar dados de entrada de dados gerados: `arquivos_csv/` só com as
      planilhas de entrada; a tabela geral de casas testadas
      (`casas_resultado.csv`, reescrita pelo programa) fora do git;
      rever `palavras_chave_res.csv` e `teste_raspagem.csv`
- [x] Tirar do repositório dados de pesquisa que não são exemplo
      (`autoria_e_tramitacao/tabela_limpa_2.csv`)
- [x] Remover código morto e comentários desatualizados que sobrarem

**Nova identidade: SAPyL — Raspador do Sistema de Apoio Legislativo.**
Projeto de código aberto que ajuda qualquer pessoa a acompanhar o que está
acontecendo em várias casas legislativas do Brasil ao mesmo tempo.
- [x] Renomear o repositório no GitHub para `sapyl`, atualizando links e o
      badge do CI; pacote Python e comando também `sapyl`
- [x] Identidade só em texto no README (nome, chamada curta, badges), sem
      logotipo
- [x] Reescrever a descrição do README e os nomes no código e na
      documentação com a nova marca
- [x] Página do projeto no GitHub Pages (`docs/`, uma página estática em
      português): o que é, para quem serve, o que produz, instalação e
      uso. Publicada por um workflow do GitHub Actions, depois da troca de
      nome do repositório (endereço `leoaucar.github.io/sapyl`).
      Publicada em <https://leoaucar.github.io/sapyl/>.

**Bugs e pendências que ficaram de fora da Fase 1**
- [x] **Autoria e tramitação não retoma:** o script só grava no fim; uma
      interrupção perde tudo. Usar o mesmo estado e gravação linha a linha
      do programa principal.
- [x] **Autoria e tramitação pela API** (`/api/materia/autoria/?materia=`,
      `/api/materia/tramitacao/?materia=`), com o HTML como reserva, como já
      é feito com as matérias.
- [x] **Modo atualização perde colunas da pessoa:** colunas acrescentadas à
      mão no resultado final (ex.: `Relevante`, anotações) não passam para o
      arquivo `_ATUALIZADO_`. Preservá-las, e reativar como opção o filtro
      "só as relevantes" (hoje comentado).
- [x] **Arquivo bruto da busca grande** (item 10 do §3; ~1 GB numa execução
      completa): guardar só os links extraídos de cada página, mantendo a
      retomada.
- [x] **Palavras de projeto retomado:** vêm do `config.json`; mudar o arquivo
      de palavras não tem efeito e ninguém é avisado. Avisar quando forem
      diferentes.
- [x] **Erros permanentes tratados como temporários:** erro de certificado
      (SSL) ou de DNS é tentado 4 vezes, com esperas. Não repetir esses.
- [x] **Retomada refaz a sondagem da API e as consultas de nomes** (tipo,
      regime): guardar a fonte de cada casa e os nomes no projeto.
- [x] **Log sem limite:** o `.log` cresce a cada retomada; separar por
      execução ou rodar o arquivo.
- [x] **Casas que redirecionam para outro domínio:** links absolutos para o
      domínio novo são descartados. Tratar os dois domínios como a mesma casa
      (se a validação confirmar o caso).
- [x] **Achados da validação da Fase 1** (lista em
      `specs/2026-10-24-runtime-improvements/validation.md`, "Issues found").

> **Situação:** Fase 1b concluída, validada contra os sites reais e no `main`
> em 27/10/2026 (veja o `validation.md` da spec). O repositório agora é
> `leoaucar/sapyl`.

### Fase 2: Velocidade (paralelismo)
O limite é **por site**, então o ganho vem de **processar várias casas ao mesmo
tempo**, nunca de acelerar dentro da mesma casa.

- [x] **Busca e raspagem com `ThreadPoolExecutor`**: um worker por casa (8
      por padrão, `paralelo` no `config.json`). Limite de 35/min por site e,
      como as casas dividem o mesmo servidor, também um limite por servidor
      (120/min, que cai pela metade se casas diferentes receberem 429).
- [x] **Pipeline em vez de etapas em lote:** cada casa faz busca, links,
      matérias e PDFs em sequência, assim as casas pequenas terminam cedo e
      não esperam as grandes. A planilha final sai igual à de uma casa por vez.
- [x] **Teste das URLs em paralelo** (limitado pelo servidor, não pelo número
      de threads).
- [x] **Downloads em paralelo** (cada casa baixa os seus), com streaming direto
      para o arquivo (`stream=True`). Baixar só as relevantes: modo
      atualização com a coluna `Relevante` e downloads.
- [ ] Evolução opcional: `asyncio` + `httpx`/`aiohttp`. Não é necessária
      enquanto o limite do servidor for o gargalo.
- (Não guardar o HTML bruto da busca: passou para a Fase 1b.)

Estimativa: a execução completa passa a ser limitada pelo servidor
compartilhado, não pela casa com mais matérias: **3 a 6 h** com 120
requisições por minuto, em vez de 10–20 h (veja a seção 2).

> **Situação:** Fase 2 concluída, validada contra os sites reais e no `main`
> em 30/10/2026 (spec [`specs/2026-10-27-paralelismo/`](specs/2026-10-27-paralelismo/),
> veja o `validation.md`). Valores padrão mantidos: 8 casas e 120 requisições
> por minuto por servidor. Nas 10 casas do Acre não houve ganho (Rio Branco
> sozinha leva ~45 min); o ganho aparece com muitas casas com trabalho.

### Fase 2b: Melhorar a usabilidade
Revisão básica da interface de linha de comando e do fluxo de trabalho do
projeto, do ponto de vista de quem pesquisa: as perguntas, as mensagens, os
arquivos que aparecem na pasta do projeto e os passos para criar, retomar e
atualizar um projeto.

- [x] Revisar as perguntas e mensagens do terminal (clareza, ordem, o que
      acontece com respostas inválidas)
- [x] Revisar o fluxo de trabalho (novo, retomar, atualizar, autoria e
      tramitação) e os arquivos gerados em cada um
- [x] Listar o que melhorar e decidir o que entra nesta fase, o que vai para
      a Fase 2c e o que vai para a Fase 7 (configuração e linha de comando)

Spec [`specs/2026-10-30-interface-terminal/`](specs/2026-10-30-interface-terminal/)
(revisão de 30/10/2026):

- [ ] Menus com as setas do teclado (`questionary`), com as mesmas perguntas
      numeradas quando o terminal não é interativo
- [ ] Menu principal: novo projeto, retomar (escolhendo da lista), atualizar,
      autoria e tramitação, ajuda, sair
- [ ] Situação de cada projeto na lista (concluído, com falhas, interrompido,
      não iniciado), sem fazer requisições
- [ ] Estados escolhidos numa lista (com o atalho Sul e Sudeste) e "todas as
      casas ou teste com 10"; aviso do tamanho dos PDFs
- [ ] Palavras-chave lidas e mostradas antes de criar o projeto; arquivo
      ausente ou errado gera uma mensagem clara, sem traceback e sem pasta
      vazia
- [ ] Tela de confirmação antes de começar (casas, buscas, PDFs): começar,
      mudar as respostas ou cancelar
- [ ] Terminal mais limpo durante a execução: barra de progresso, casas em
      andamento e tempo restante estimado (`rich`); o detalhe vai só para o log
- [ ] Resumo com os próximos passos e a oferta de buscar autoria e tramitação
      do resultado logo em seguida

### Fase 2c: Fluxo de trabalho e novas opções
O que a revisão da Fase 2b encontrou no fluxo de trabalho e ficou para depois
da interface (lista em `specs/2026-10-30-interface-terminal/spec.md`, §9).
Decidir na spec o que vai para a Fase 7.

**Novas opções no menu**
- [ ] **Ampliar um projeto:** acrescentar palavras-chave ou estados a um
      projeto existente, buscando só o que é novo e sem raspar de novo as
      matérias que já estão lá (hoje é preciso criar outro projeto)
- [ ] **Só contar os resultados:** fazer as buscas sem raspar as matérias e
      mostrar quantos resultados cada palavra traz em cada casa, para testar
      as palavras gastando pouco
- [ ] **Baixar os PDFs depois:** baixar os textos de um projeto já pronto
      (todos ou só os `Relevante`), sem raspar tudo de novo como no modo
      atualização
- [ ] **Testar a lista de casas** sozinha, fora de um projeto novo
- [ ] **Configurações** no menu (casas ao mesmo tempo, limite por servidor),
      em vez de editar o `config.json`

**Arquivos e fluxo**
- [ ] **Planilha que o Excel abre direito:** hoje o CSV sai em UTF-8 sem BOM
      e separado por vírgula, e o Excel em português mostra os acentos
      errados e tudo numa coluna. Gravar também um `.xlsx` ou um CSV que o
      Excel lê corretamente
- [ ] **Pasta do projeto mais limpa:** o resultado final fica no meio dos
      arquivos internos (estado, páginas, links, matérias, cache, logs…); levar os internos para uma subpasta, lendo os
      projetos antigos como estão
- [ ] **Rodar o `sapyl` de qualquer pasta:** a planilha de casas junto com o
      pacote e o arquivo de palavras num lugar conhecido (ou copiado para o
      projeto ao criá-lo, para o projeto ficar completo)
- [ ] **Retomar a busca da última página**, em vez de começar da página 1
- [ ] **Modo atualização:** um arquivo `_ATUALIZADO_<dd_mm_aaaa>` por
      execução (data num formato diferente do dos logs, `aaaa-mm-dd`); os
      arquivos se acumulam
- [ ] **Autoria e tramitação:** onde fica a saída (ao lado da entrada) e o
      nome do arquivo

### Fase 3: Saída em banco SQL e armazenamento de documentos
- [ ] Gravar os resultados em **SQLite** (padrão, um arquivo `.db` por projeto)
      ou **PostgreSQL** (configurável), usando SQLAlchemy
- [ ] Esquema proposto:
  - `casas` (id, uf, municipio, url, ativa, verificada_em)
  - `buscas` (id, projeto, palavra, casa_id, executada_em)
  - `materias` (id, casa_id, sapl_id, tipo, numero, ano, titulo, ementa,
    data_apresentacao, link, texto_original, raspada_em,
    **UNIQUE(casa_id, sapl_id)**)
  - `materia_palavra` (materia_id, busca_id): de qual busca veio cada matéria
  - `autorias` e `tramitacoes` (materia_id, ...)
- [ ] `UPSERT` para atualizar matérias sem duplicar
- [ ] Manter a exportação para CSV/Excel a partir do banco
- [ ] **Documentos fora do banco relacional (parte NoSQL):** os PDFs e outros
      arquivos das matérias (textos originais, anexos, documentos acessórios)
      e o texto extraído deles ficam num armazenamento de documentos, e o SQL
      guarda só a referência (`documentos`: materia_id, tipo, url de origem,
      chave no armazenamento, tamanho, hash, baixado_em)
  - Padrão local, sem servidor: a pasta do projeto, com os arquivos
    nomeados pelo hash (o mesmo PDF achado duas vezes é guardado uma vez)
  - Opções configuráveis: **MongoDB** (GridFS para os arquivos, uma coleção
    com o texto extraído e os metadados de cada documento) ou um
    armazenamento de objetos compatível com S3 (**MinIO** local, **S3** na
    nuvem, Fase 7)
  - Uma interface única (`guardar`, `abrir`, `existe`, `apagar`) para os
    downloads e para a busca no conteúdo (Fase 6) não dependerem de onde os
    arquivos estão
  - Migração dos projetos atuais: importar a pasta `downloads/` sem baixar
    nada de novo

### Fase 3b: Sugestão de palavras-chave
A pessoa descreve o tema ou dá algumas palavras, e o programa sugere variações
e termos relacionados. Vem depois da Fase 3 porque a abordagem principal
aprende com as matérias já coletadas no banco.

**Spec principal (sem dependências pesadas, tudo offline):**
- [ ] **Variações de grafia:** plurais, com e sem acento, com hífen e com
      espaço, erros de digitação comuns (a própria lista atual tem
      "politico-partidario" / "politico partidario" e o erro
      "aparellhamento"). Python puro + stemmer RSLP do NLTK para português.
- [ ] **Aprender com os dados coletados:** a partir de `Ementa` e
      `Indexacao` das matérias no banco, sugerir termos que aparecem junto
      com as palavras da pessoa (TF-IDF ou contagem de coocorrência, com
      scikit-learn). Usa o vocabulário real das casas legislativas.
- [ ] **Revisão obrigatória:** a pessoa revisa e edita a lista antes da
      busca. Cada termo a mais multiplica as buscas, e todas contam no
      limite de 35 requisições/min de cada site.
- [ ] **Teste rápido de cada termo:** uma página de busca em poucas casas,
      mostrando quantos resultados cada termo traz, para descartar cedo os
      termos inúteis.

**Opções para specs futuras (plugins opcionais):**
- [ ] **Embeddings locais** (`sentence-transformers` com modelo
      multilíngue, offline): entende o sentido ("escola sem partido" perto
      de "doutrinação ideológica"). Contra: download de centenas de MB e
      instalação mais pesada.
- [ ] **LLM por API** (ex.: Claude): o melhor encaixe para "a pessoa
      descreve o que quer → lista de termos". Contra: serviço externo, com
      chave de API, custo e necessidade de internet, num software livre que
      pesquisadores rodam por conta própria.
- (Avaliado e deixado de lado por ora: dicionário de sinônimos
  OpenWordnet-PT, que traz sinônimos da língua geral, não do jargão
  legislativo.)

### Fase 4: Interface web básica (HTML + CSS + JS)
- [ ] API pequena (**FastAPI** ou **Flask**) sobre o banco da Fase 3
- [ ] Páginas em HTML, CSS e JavaScript puro (sem framework):
  - **Novo projeto:** formulário com as palavras-chave, os estados e o limite
    de casas
  - **Acompanhamento:** progresso da execução (casas concluídas, matérias,
    erros), atualizado por polling
  - **Resultados:** tabela com filtros por UF, casa, ano, tipo e palavra,
    busca no texto da ementa e link para o PDF (a busca completa, em todos os
    campos e no conteúdo, vem na Fase 6)
  - **Exportação:** botões para CSV/Excel
  - **Marcar relevância:** coluna "Relevante" editável, que alimenta o modo
    atualização e os downloads seletivos
- [ ] Servir a interface como arquivos estáticos (primeiro localmente; S3 +
      CloudFront quando houver a versão em nuvem, Fase 7)

### Fase 5: Qualidade
- [x] Testes automatizados (`pytest`) com páginas HTML salvas, sem acessar a
      rede
- [x] Verificar a compatibilidade com o pandas 3 (o CI roda com pandas 2 e 3)
- [ ] Fixar versões testadas (`requirements.lock`)
- [x] CI no GitHub Actions (testes, `ruff` e instalação limpa)

### Fase 6: Busca nos resultados e mais critérios de busca
Duas partes. A primeira: depois de coletar, a pessoa precisa achar o que
interessa dentro do que veio, com uma busca que filtra o banco de um projeto
(Fase 3) por palavras, por qualquer campo ou pelo conteúdo do texto das
matérias, tudo local, sem nenhuma requisição aos sites do SAPL. A segunda:
coletar também por outros critérios além das palavras-chave, como a autoria.

**Busca nos resultados (local)**

- [ ] **Palavras em qualquer campo ou num campo escolhido:** título, ementa,
      indexação, tipo, número, ano, data, casa, UF, palavras da busca,
      autoria e tramitação. Mesma sintaxe das palavras-chave (expressão
      exata, termos juntos com vírgula), mais `OU` e exclusão (`-termo`)
- [ ] **Filtros combinados:** UF, casa, tipo, período de apresentação, situação
      (`Em Tramitacao`), status da raspagem e `Relevante`
- [ ] **Busca no conteúdo:** extrair o texto dos PDFs baixados (`pypdf` ou
      `pdfminer.six`) para uma tabela `textos` (materia_id, texto, método,
      extraído em), com o trecho encontrado em destaque. PDFs escaneados ficam
      marcados como "sem texto"; OCR (Tesseract) como plugin opcional
- [ ] **Índice de texto completo** no SQLite (FTS5, com o `unicode61` sem
      acentos: "orçamento" acha "orcamento"), ordenado por relevância (bm25);
      no PostgreSQL, `tsvector` com o dicionário `portuguese`
- [ ] **Onde usar:** uma opção no menu do programa (e, depois, na linha de
      comando) e a tela de resultados da interface web (Fase 4)
- [ ] **Saída:** exportar o resultado filtrado para CSV/Excel, marcar as
      matérias encontradas como `Relevante` (alimenta o modo atualização e os
      downloads seletivos) e salvar buscas para repetir depois
- [ ] Testes com um banco pequeno de exemplo e PDFs de fixture (com e sem
      texto), sem acessar a rede

**Mais critérios de busca nos sites (na coleta)**

Hoje a coleta só pesquisa palavras-chave (`/sistema/search/`). O SAPL tem
outras formas de achar matérias, que podem trazer o que a pessoa quer sem
depender das palavras da ementa.

- [ ] **Reavaliar os sites atuais** antes de decidir: numa amostra de casas
      (por estado e por versão do SAPL), ver quais filtros existem e
      funcionam na pesquisa de matérias (`/materia/pesquisar-materia`) e na
      API (`/api/materia/materialegislativa/?…`), quanto custam em
      requisições e se os resultados batem com a página. Registrar o que
      cada versão aceita; casas sem o filtro continuam só com palavras
- [ ] **Buscar por autoria:** por parlamentar, comissão ou Executivo
      (ex.: "todas as matérias de autoria do prefeito"), com a lista de
      autores de cada casa (`/api/base/autor/`) para a pessoa escolher pelo
      nome
- [ ] **Outros critérios, se os sites permitirem:** tipo de matéria, ano ou
      período de apresentação, situação (em tramitação ou não), regime,
      assunto/indexação e número
- [ ] **Combinar** os critérios com as palavras-chave (ex.: palavra +
      tipo + período), guardados no projeto como as palavras de hoje, com
      a mesma retomada e o mesmo limite de requisições
- [ ] Testes com respostas salvas dos filtros (fixtures), sem acessar a rede

### Fase 7: Configuração e execução em nuvem
- [ ] Trocar as perguntas interativas por **configuração em arquivo**
      (`config.yaml`) e **linha de comando** (`argparse`), mantendo o modo
      interativo como opção
- [ ] Variáveis de ambiente para credenciais (URL do banco, bucket)
- [ ] **Dockerfile** para rodar em qualquer nuvem (VM, AWS ECS/Fargate,
      Google Cloud Run Jobs)
- [ ] **AWS Lambda:**
  - Uma Lambda tem limite de **15 min** por execução, então o trabalho precisa
    ser dividido.
  - Uma função *orquestradora* coloca uma mensagem por casa (ou por casa e
    palavra) numa fila **SQS**.
  - Funções *workers* consomem a fila, cada uma com uma casa, o que também
    respeita o limite por site.
  - Resultados vão para **RDS/Aurora PostgreSQL** ou **DynamoDB**, e os PDFs
    para o **S3**.
  - Agendamento pelo **EventBridge** (ex.: atualização semanal).
  - Infraestrutura como código com **AWS SAM** ou **Terraform**.
- [ ] Alternativa mais simples para execuções longas: **ECS Fargate** ou
      **AWS Batch** com o mesmo contêiner, sem o limite de 15 min
