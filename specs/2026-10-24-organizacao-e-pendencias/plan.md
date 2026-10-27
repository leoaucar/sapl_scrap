# Plan: Code organization, SAPyL identity and leftover issues

- **Spec:** [spec.md](spec.md) · **Status:** Approved 2026-10-27 · **Date:** 2026-10-24
- **Branch for implementation:** `spec/2026-10-24-organizacao-e-pendencias`,
  from `main` **after** the runtime-improvements branch is merged

## 1. Approach in one paragraph

First freeze a small project folder made by the Phase 1 code as a test
fixture, so compatibility can be checked after every later step. Then move
the code into a `sapyl` package in small, behaviour-preserving steps. Each
step is a pure move or rename with the full suite green, and lint and format
are added at the end of the move. Only then fix the leftover issues, one task
each, on top of the new layout. The repository is renamed on GitHub last,
after the merge, because GitHub redirects the old URLs.

## 2. Findings used by this plan (2026-10-24)

Checked on Cascavel/PR with 6 API requests, plus the Phase 1 fixtures from
Rio Branco:

| Topic | Finding | Consequence |
|---|---|---|
| Authors API | `/api/materia/autoria/?materia=<id>` → paginated list (`results`, `pagination.total_entries`) with `autor` id and `primeiro_autor` | 1 request per matter + cached author lookups |
| Author names | `/api/base/autor/<id>/` → `nome`, `cargo`, `tipo` (id); `/api/base/tipoautor/<id>/` → `__str__` ("Parlamentar") | `Autoria` = `nome (tipo)`, same as HTML "Autor (Descrição)" |
| Author text (checked 2026-10-27, T02) | the HTML author column is the API `__str__`, which is `nome - cargo` when `cargo` is set ("Executivo Municipal - sapladm"), else `nome` | use `__str__`, not `nome`, so API and HTML give the same `Autoria` |
| Procedure API | `/api/materia/tramitacao/?materia=<id>` → newest first (same order as the HTML table, checked on both houses) | first result = latest step |
| Procedure names | `status` → `/api/materia/statustramitacao/<id>/` (`descricao`); units → `/api/materia/unidadetramitacao/<id>/` (`__str__`) | cached lookups, like `tipo`/`regime` today |
| Staff data | list items carry `ip`, `user` | never stored; removed from fixtures |

The equivalence between API and HTML text for units and statuses is
checked by a test (TR-3). If they differ, the API text is used and the
difference is documented.

## 3. Package layout

```
sapyl/
  __init__.py            __version__
  __main__.py            python -m sapyl
  cliente_http.py        (was http_sapl.py; not "http" to avoid confusion with the stdlib)
  registro.py            log setup (per run) and summary
  colunas.py             COLUNAS_FINAIS, COLUNAS_MATERIAS, COLUNAS_LINKS, COLUNAS_CASAS, ETAPAS
  estado.py              Estado, ArquivoCSV, ler_csv, Cache (fontes + nomes, JSON)
  projeto.py             Projeto, abrir_ou_criar, config (was gerenciador_projetos.py)
  casas.py               (was casas_legislativas.py)
  palavras.py            (was palavras_chave.py)
  busca.py               (was buscador.py)
  links.py               normalizar_link, deduplicar_links, links_da_pagina (from materias.py + raspador.py)
  materias/
    __init__.py          raspar_materia, raspar_todas, Fontes
    valores.py           limpar, data_br, data_hora_br, sim_nao, esquema_da_casa
    api.py               extrair_api, Consultas
    html.py              extrair_html
  tabela.py              montar_final, salvar/ler final (was tratamento_resultado.py)
  downloads.py           (was download_pdf.py)
  autoria.py             authors and procedure: API + HTML, resume
  interface/
    entrada.py           prompts
    principal.py         menu, flows (new/resume, update, authors), main(), executar()
programa.py              shortcut: from sapyl.interface.principal import executar
```

Layers, from the bottom up. A module may import from its own group and from
groups to its left, never from groups to its right:

1. `registro`, `colunas`
2. `cliente_http`, `estado`
3. `casas`, `palavras`, `links`
4. `busca`, `materias`, `autoria`
5. `tabela`, `downloads`
6. `projeto`
7. `interface`

`autoria.py` only processes a given input CSV into an output CSV. Choosing
a project and its latest final file belongs to `interface`. A test checks
the rule with a simple AST scan of the imports.

## 4. Packaging and tooling

- `pyproject.toml`:
  - `[build-system]` setuptools.
  - `[project]` `name = "sapyl"`, `requires-python = ">=3.10"`, runtime
    dependencies as today, `optional-dependencies.dev = [pytest, pytest-cov, ruff]`,
    `license = {file = "LICENSE"}`, authors from `AUTHORS.md`.
  - `[project.scripts] sapyl = "sapyl.interface.principal:executar"`.
  - `[tool.setuptools.packages.find] include = ["sapyl*"]`.
  - `[tool.ruff]` `line-length = 100`, `target-version = "py310"`.
  - `[tool.ruff.lint] select = ["E", "F", "W", "I", "B", "UP"]`.
  - `[tool.ruff.format] quote-style = "single"`.
  - Existing pytest/coverage sections (`--cov=sapyl`).
- `requirements.txt` → `.`, and `requirements-dev.txt` → `-e .[dev]`.
  Both are kept so older instructions still work.
- `executar()` handles one argument, `--version`. Anything else prints a
  short usage note. Real CLI options come with the config & CLI spec.
- CI (`tests.yml`) has two jobs:
  - `testes`: matrix 3.10/3.12, `pip install -e .[dev]`, `ruff check`,
    `ruff format --check`, `pytest`.
  - `instalacao`: 3.12, clean `pip install .`, then `sapyl --version` and
    `python -m sapyl --version`.

## 5. Moving the code (behaviour-preserving)

1. `git mv` each module to its new path, so history is kept. Imports become
   absolute (`from sapyl.estado import Estado`). Tests are updated in the same
   commit. The suite must stay green with **no assertion changes**.
   One-to-one moves in T04, with the later splits in T06:

   | Phase 1 file | T04 | T06 |
   |---|---|---|
   | `http_sapl.py` | `sapyl/cliente_http.py` | |
   | `registro.py`, `estado.py` | `sapyl/registro.py`, `sapyl/estado.py` | |
   | `casas_legislativas.py` | `sapyl/casas.py` | |
   | `palavras_chave.py` | `sapyl/palavras.py` | |
   | `buscador.py` | `sapyl/busca.py` | |
   | `raspador.py` | `sapyl/links.py` | + link functions from `materias` |
   | `materias.py` | `sapyl/materias.py` | → `sapyl/materias/` subpackage |
   | `tratamento_resultado.py` | `sapyl/tabela.py` | |
   | `download_pdf.py` | `sapyl/downloads.py` | |
   | `gerenciador_projetos.py` | `sapyl/projeto.py` | |
   | `entrada.py` | `sapyl/entrada.py` | → `sapyl/interface/entrada.py` |
   | `programa.py` | `sapyl/principal.py` (+ new shortcut `programa.py`) | → `sapyl/interface/principal.py` |
   | `autoria_e_tramitacao/autoria_e_tramit.py` | `sapyl/autoria.py` | |
2. Extract `colunas.py` (FR-4): every list of column names or stages lives
   there. The other modules import from it.
3. Split `materias.py` into the subpackage (`valores`, `api`, `html`,
   `__init__`) and move link functions to `links.py`.
4. Create `interface/` (`entrada`, `principal`), `__main__.py`, the console
   script and the `programa.py` shortcut.
5. Type hints and docstrings on public functions (FR-5), then
   `ruff format` and `ruff check --fix`. Remaining lint issues are fixed by hand.
6. Layer test (§3).

`tests/apoio.py` patches nothing by module path, so moving it needs only
import changes. `monkeypatch.setattr(materias, 'raspar_materia', …)` in two
tests becomes `sapyl.materias`.

## 6. Data and identity

- `git rm --cached arquivos_csv/casas_resultado.csv autoria_e_tramitacao/tabela_limpa_2.csv`
  and add both to `.gitignore`, with a comment explaining why (FR-8, FR-9).
- `git rm arquivos_csv/palavras_chave_res.csv`. New
  `arquivos_csv/exemplo_palavras_chave.csv` (UTF-8, no BOM):

  ```
  Palavras
  orçamento
  plano diretor
  lei orgânica
  "orçamento, emenda impositiva"
  saneamento básico
  saneamento basico
  ```

  README table: line → query (`plano diretor` → `"plano+diretor"`;
  `orçamento, emenda impositiva` → `"orçamento"+"emenda+impositiva"`, meaning
  both terms together). It also explains that spelling variants go on separate
  lines and that each line is one more search per house, so it counts toward
  the rate limit. To use the example, the researcher copies it to
  `palavras_chave.csv`.
- `arquivos_csv/exemplo_palavras_chave_educacao.csv` is made from the old
  `palavras_chave_res.csv` by a small, reviewable diff: BOM removed,
  `aparellhamento ideologico` → `aparelhamento ideologico`, double spaces
  after commas collapsed (`"professor, conviccoes morais"`). The 23 lines stay
  in the same order. The README describes it as a real research list (23
  searches per house, ~1 hour for 10 houses with the rate limit).
- README header:

  ```
  # SAPyL
  **Raspador do Sistema de Apoio Legislativo**
  Acompanhe, num só lugar, o que está tramitando em dezenas de câmaras e
  assembleias brasileiras que usam o SAPL. Software livre (AGPL-3.0).
  [badges]
  ```

  It's followed by "Para que serve" (who it is for, what it produces), then
  the existing sections, updated for `pip install .` and `sapyl`.
- `User-Agent`: `SAPyL/<versão> (pesquisa; +https://github.com/leoaucar/sapyl)`.
- `AUTHORS.md` citation title: *SAPyL: Raspador do Sistema de Apoio Legislativo*.
- The rename on GitHub (FR-12) is the last task, after the merge:
  `gh repo rename sapyl`, then `git remote set-url origin …`, then update the
  badge/clone URLs in one commit on `main`. **It needs the user's go-ahead
  at that moment** (it is an external, visible action).

## 7. Leftover issues

### 7.1 SSL and DNS (FR-24) — `cliente_http.py`

- `requests.exceptions.SSLError` → reason `ssl`, returned at once.
- A `ConnectionError` whose cause chain contains
  `urllib3.exceptions.NameResolutionError` or `socket.gaierror` → reason
  `dns`, returned at once.
- Helper `_causas(exc)` walks `__cause__`, `__context__` and `args` (with a
  depth limit). Tests build these exception chains by hand.

### 7.2 Per-run logs (FR-26) — `registro.py`

- `configurar(pasta_projeto, nome, modo)` writes
  `<pasta>/logs/<nome>_<aaaa-mm-dd_hhmmss>_<modo>.log`, where `modo` is
  `novo`, `retomada`, `atualizacao` or `autoria`, and returns the path. The
  summary's last line shows it.
- Validation scripts read every file in `logs/`, plus the old `<nome>.log`
  if it's there.

### 7.3 Cache of sources and names (FR-25) — `estado.Cache`

- `<nome>_proj/cache.json`: `{"fontes": {host: "api"|"html"}, "nomes": {url: nome}}`.
- It's loaded at start, and each new entry is saved right away by writing a
  temp file and renaming it.
- `Fontes` and `Consultas` (and the autoria lookups) receive the cache.
  Failed lookups are **not** cached, so they are retried on the next run.
- If the file is corrupt, it's ignored with a warning and the run starts
  with an empty cache.

### 7.4 Keywords warning (FR-23) — `interface/principal.py`

- On resume, if `arquivos_csv/palavras_chave.*` exists, prepare its terms and
  compare them with `config['palavras']`. Missing and new terms are logged
  as a warning with the advice to create a new project. The run continues
  with the saved terms.

### 7.5 Search file without HTML (FR-21, FR-22) — `busca.py`, `links.py`

- New file `<nome>_paginas_busca.csv`: `Casa, Palavra, Pagina, links, link`,
  where `links` holds the canonical links separated by spaces. It's written
  per page, as today.
- `links_do_projeto(projeto)` reads the new file and, if present, the old
  raw file (parsing its HTML as in Phase 1), in that order. Deduplication
  works as today.
- The old file is never written by the new version.

### 7.6 Redirects (FR-27) — `casas.py`, `links.py`

- Availability test: if `resposta.bruta.url` has a different scheme or host
  than the house URL, `url_final = <scheme>://<host>/`. The house table gains
  a `url_final` column. Old tables are read with it empty.
- One helper `base_da_casa(casa)` returns `url_final or url`. Search,
  matters, downloads and autoria use it for requests.
- `Link Casa` and the matter key stay on the **original** URL and host, so
  keys don't change for existing projects. `normalizar_link` accepts links
  on either host.
- If the Phase 1 validation shows no redirecting house, this still ships.
  It's tested offline, and the validation records that it was not seen in
  practice.

### 7.7 Update mode (FR-19, FR-20) — `interface/principal.py`, `tabela.py`

- Extra columns = input columns not in `COLUNAS_FINAIS` (and not
  `Unnamed: *`). After `montar_final`, they're joined by key and appended
  after `COLUNAS_FINAIS`. Rows keep the input order.
- If `Relevante` exists, the prompt asks: *"Atualizar só as matérias
  marcadas como relevantes? 1- sim, 2- não"*. The filter uses the
  normalised values from FR-20, and the log records how many rows were
  kept.

### 7.8 Authors and procedure (FR-14 to FR-18) — `autoria.py`

- Per matter, with `Fontes` per house (same rule as matters: switch to HTML
  on a final 404 or a non-JSON body):
  - API: autoria list → for each item, author lookup (`nome`, `tipo`) →
    tipoautor lookup. The tramitação list's first item gives status, local
    unit and destination unit lookups. ISO date → `dd/mm/aaaa`.
  - HTML: the Phase 1 parsing (by header names), unchanged.
- Rows (`chave, Autoria, Tramite, status_autoria, status_tramitacao,
  erro_autoria_tramitacao, fonte`) are appended to
  `<saida>_parcial.csv`. Progress goes to `<saida>_estado.csv` (stage
  `autoria`). On resume, keys already `ok` for both are skipped.
- At the end, the latest row per key is joined to the input by key and
  written to `<entrada>_autoria_tramitacao.csv`.
- Menu: the first question becomes `1- novo projeto ou retomar`,
  `2- atualizar um projeto`, `3- autoria e tramitação`. Option 3 asks for a
  project name *or* a CSV path. For a project, it uses its latest final
  (`_ATUALIZADO_` if there is a newer one). Output and state go in the
  project folder, or next to the CSV.
- `autoria_e_tramitacao/` is removed (FR-7). Its README section is
  rewritten.

### 7.9 Phase 1 validation findings (FR-28)

Listed in spec §9 when the Phase 1 validation ends. Each becomes a task
(T20.x) with a test.

## 8. Testing (spec §6)

- **Phase 1 project fixture (TR-4).** `tests/fixtures/projeto_fase1/` is
  created by running the **Phase 1 code** (before the move) against
  `SaplFalso` with two houses. A script
  `tests/fixtures/gerar_projeto_fase1.py` documents how; it is kept only for
  the record, because it imports Phase 1 modules that won't exist afterwards.
  The folder holds `config.json`, the state file, the old raw file, the
  links, matters and final CSVs, and `<nome>.log`, with one matter in
  `erro`.
- **New API fixtures (TR-2).** autoria, autor, tipoautor, tramitação,
  statustramitacao and unidadetramitacao from Cascavel and Rio Branco
  (≤ 15 requests per house), with `ip`/`user` removed. They're listed in
  `index.json`.
- New/changed test modules:

  | Module | Covers |
  |---|---|
  | `test_cliente_http.py` | (moved) + `ssl` / `dns` without retry, other connection errors still retried |
  | `test_registro.py` | (moved) + per-run log names, summary shows log path |
  | `test_estado.py` | (moved) + `Cache` load/save/corrupt file/failed lookups not cached |
  | `test_busca.py`, `test_links.py` | links-only page file; old raw file still read; size check on a fixture page |
  | `test_casas.py` | (moved) + `url_final` on redirect, old table without the column |
  | `test_autoria.py` | API path, HTML fallback, API≡HTML text (TR-3), resume, project vs CSV input, output join |
  | `test_principal.py` | menu with 3 options, keywords warning, update keeps extra columns, `Relevante` filter |
  | `test_compat_fase1.py` | resume and update of `projeto_fase1` (TR-4) |
  | `test_camadas.py` | no import from a lower layer |
  | `test_ponta_a_ponta.py` | extended (TR-7) |
  | `test_instalacao.py` | `executar(['--version'])`, `python -m sapyl --version` via `subprocess` |

## 9. Implementation order

1. Branch, Phase 1 project fixture, new API fixtures.
2. Packaging + CI jobs (still on the flat layout, so CI catches any break).
3. Move to the package (§5, steps 1–6), each step a commit with a green suite.
4. Data and identity (§6, without the rename).
5. Leftovers: SSL/DNS → logs → cache → keywords warning → search file →
   redirects → update mode → authors/procedure.
6. Phase 1 validation findings.
7. End-to-end extension, docs, `validation.md` alignment.
8. Validation, merge, then rename on GitHub (with the user's go-ahead).

## 10. Risks

| Risk | Mitigation |
|---|---|
| The move breaks something subtle (imports, `monkeypatch` paths) | Pure moves first, no assertion changes, Phase 1 project fixture checked after each step |
| Ruff reformatting creates a huge diff that hides real changes | Formatting in its own commit (T07), nothing else in it |
| API unit/status names differ from HTML text | Equivalence test; if they differ, document and prefer the API |
| Researchers have scripts calling `python programa.py` | Shortcut kept; README shows both |
| GitHub rename breaks clones | GitHub redirects old URLs; `git remote set-url` documented in README |
| Cache becomes stale (a house gains an API) | Cache is per project; a new project probes again |
| `palavras_chave.xlsx` is both the default input and a tracked file, so editing it shows as a git change | Accepted for now; the README suggests using `palavras_chave.csv` (untracked, has priority) for one's own lists. Revisit with the config spec |

## 11. Decisions taken in this plan (for review)

- Module named `cliente_http.py`, not `http.py` (§3).
- Version starts at `0.2.0` (Phase 1 = 0.1, never tagged).
- `--version` is the only command-line option in this spec (§4).
- The first prompt becomes a 3-option menu (§7.8). Validation scripts and the
  README are updated.
- Keys stay on the original house URL even when it redirects (§7.6).
- `palavras_chave_res.csv` replaced by a neutral example file, plus the old
  list cleaned as an alternative test (Q1).
