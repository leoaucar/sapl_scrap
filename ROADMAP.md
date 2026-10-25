# Roadmap

Diagnóstico e plano de evolução do `sapl_scrap`, a partir da avaliação do
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

A tabela tem **~840 casas**. Os resultados se concentram nas casas grandes
(assembleias e capitais). No teste, 2 das 10 casas deram 100% das matérias.

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

Hoje a execução parece mais rápida que isso só porque as requisições
bloqueadas falham na hora e viram linhas vazias.

## 3. Bugs e riscos conhecidos

Em ordem de prioridade:

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

- [ ] Detectar `HTTP 429` (e outros status ≠ 200) na raspagem das matérias e
      na busca
- [ ] Esperar o tempo de `Retry-After` (60 s) e tentar de novo, com número
      máximo de tentativas
- [ ] Respeitar o limite de 35 requisições por minuto por casa (assim o 429
      nem chega a acontecer)
- [ ] Nunca gravar a página de erro como matéria: marcar a linha com
      `status = erro` e listar as falhas no fim da execução
- [ ] Testar de novo com as 10 casas do teste: 0 matérias vazias esperadas

### Fase 1: Correção e robustez
- [ ] Sessão HTTP única (`requests.Session`) com `timeout` e retentativas
      (`urllib3.Retry` respeitando `Retry-After` para 429/5xx)
- [ ] Limitador de taxa por casa (35 req/min, configurável)
- [ ] Registrar falhas em uma coluna `status` em vez de gravar linhas vazias
- [ ] Corrigir os seletores (`div_id_data_apresentacao` etc.)
- [ ] Remover duplicatas antes de raspar e de baixar
- [ ] Logging (`logging`) em vez de `print`, com um arquivo de log por projeto
- [ ] Retomar uma execução interrompida (pular matérias já raspadas)

### Fase 1b: Organização geral do código
Próxima spec depois das melhorias de execução (Fase 1). A Fase 1 só reorganiza
o necessário para testar; esta fase arruma a estrutura antes do paralelismo.

- [ ] Transformar o projeto em um pacote Python (`sapl_scrap/`) com
      `pyproject.toml`, separando camadas: HTTP, busca, matérias (API/HTML),
      downloads, estado/projeto, interface (perguntas)
- [ ] Um único ponto de entrada (`python -m sapl_scrap`), mantendo
      `programa.py` como atalho
- [ ] Trazer `autoria_e_tramitacao/` para dentro do pacote
- [ ] Nomes consistentes (funções, colunas, arquivos de saída) e um único
      lugar para definir as colunas do resultado
- [ ] Tipagem (type hints) e docstrings nas funções públicas
- [ ] Formatação e lint automáticos (`ruff`) rodando também no CI
- [ ] Remover código morto e comentários desatualizados que sobrarem
- [ ] **Nova identidade: Puxa Projeto Sapl.** Projeto de código aberto que
      ajuda qualquer pessoa a acompanhar o que está acontecendo em várias
      casas legislativas do Brasil ao mesmo tempo.
  - [ ] Renomear o repositório no GitHub para `puxa_projetos_sapl`
        (e o pacote Python, se for o caso), atualizando links e o badge do CI
  - [ ] Pequena identidade visual para o README (nome, logotipo simples,
        cores)
  - [ ] Reescrever a descrição do README e os nomes no código e na
        documentação com a nova marca

### Fase 2: Velocidade (paralelismo)
O limite é **por site**, então o ganho vem de **processar várias casas ao mesmo
tempo**, nunca de acelerar dentro da mesma casa.

- [ ] **Busca e raspagem com `ThreadPoolExecutor`**: um worker por casa
      (10 a 30 threads). Cada casa tem o seu limitador e a sua fila. É um
      trabalho de rede, então threads bastam (o GIL não atrapalha).
- [ ] **Pipeline em vez de etapas em lote:** cada casa faz busca, links,
      matérias e PDFs em sequência, assim as casas pequenas terminam cedo e
      não esperam as grandes.
- [ ] **Teste das URLs em paralelo** (de ~70 min para ~1–2 min com 50 threads).
- [ ] **Downloads em paralelo**, com streaming direto para o arquivo
      (`stream=True`) e opção de baixar só as matérias marcadas como relevantes.
- [ ] Evolução opcional: `asyncio` + `httpx`/`aiohttp` para milhares de
      conexões simultâneas.
- [ ] Não guardar o HTML bruto da busca, só os links extraídos.

Estimativa com 20 casas em paralelo: a execução completa passa a ser limitada
pela casa com mais matérias, algo como **30–60 min**, em vez de 10–20 h.

### Fase 3: Saída em banco SQL
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

### Fase 4: Configuração e execução em nuvem
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

### Fase 5: Interface web básica (HTML + CSS + JS)
- [ ] API pequena (**FastAPI** ou **Flask**) sobre o banco da Fase 3
- [ ] Páginas em HTML, CSS e JavaScript puro (sem framework):
  - **Novo projeto:** formulário com as palavras-chave, os estados e o limite
    de casas
  - **Acompanhamento:** progresso da execução (casas concluídas, matérias,
    erros), atualizado por polling
  - **Resultados:** tabela com filtros por UF, casa, ano, tipo e palavra,
    busca no texto da ementa e link para o PDF
  - **Exportação:** botões para CSV/Excel
  - **Marcar relevância:** coluna "Relevante" editável, que alimenta o modo
    atualização e os downloads seletivos
- [ ] Servir a interface como arquivos estáticos (S3 + CloudFront na versão em
      nuvem)

### Fase 6: Qualidade
- [ ] Testes automatizados (`pytest`) com páginas HTML salvas, sem acessar a
      rede
- [ ] Fixar versões testadas (`requirements.lock`) e verificar a compatibilidade
      com o pandas 3
- [ ] CI no GitHub Actions
