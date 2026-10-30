# Tech stack — SAPyL (formerly sapl_scrap)

Current stack, and what is planned for later specs. Changing anything in
"Current" requires a note in the spec's plan.

## Current

| Area            | Choice                                   | Notes                                      |
|-----------------|------------------------------------------|--------------------------------------------|
| Language        | Python ≥ 3.10                            | CI on 3.10 (pandas 2) and 3.12 (pandas 3)  |
| Packaging       | `pyproject.toml` (setuptools ≥ 77)       | Package `sapyl`, command `sapyl`, `python -m sapyl`; version in `sapyl/__init__.py` |
| HTTP            | `requests` (+ `urllib3`, bundled)        | One client per run, in `sapyl/cliente_http.py` only; one `Session` per thread |
| Concurrency     | Threads: `concurrent.futures.ThreadPoolExecutor`, `threading` | One house per worker (`sapyl/execucao.py`); limits shared in the client under one lock |
| HTML parsing    | `beautifulsoup4` with `html.parser`      | Explicit parser, no extra dependency       |
| Tables / output | `pandas` (≥ 2.1, works with 3.x), CSV    | `openpyxl` for reading `.xlsx` inputs      |
| Project storage | CSV (append-only state), JSON (`config.json`, `cache.json`) | Atomic writes for JSON (temp file + rename) |
| Logging         | `logging` (standard library)             | Terminal + one file per run in `<projeto>/logs/` |
| Interface       | Interactive terminal (`input()`), 3-option menu | Replaced by config/CLI in a later spec; only `--version` today |
| Tests           | `pytest` (dev extra)                     | Offline; fixtures under `tests/fixtures/`; AST checks for layers, column lists and type hints |
| Coverage        | `pytest-cov` (dev extra)                 | Report only, no threshold (≥ 95 % expected) |
| Lint / format   | `ruff` (dev extra)                       | `line-length = 100`, single quotes; enforced in CI |
| CI              | GitHub Actions                           | `testes` (ruff + pytest, 3.10/3.12), `instalacao` (clean install), `pagina` (Pages deploy from `docs/`) |
| Project site    | `docs/`: plain HTML + CSS + JavaScript   | No libraries, no external files; JS only adds extras |
| Dependencies    | `pyproject.toml` (`dev` extra)           | `requirements*.txt` are thin wrappers      |

## Package layout

Layers from the bottom up; a module imports only from its own layer and the
ones below (checked by `tests/test_camadas.py`):

1. `registro` (log, summaries), `colunas` (every column list and state stage),
   `padroes` (every limit and default, `paralelo` check)
2. `cliente_http` (rate limit, retries), `estado` (state file, `Cache`)
3. `casas`, `palavras`, `links` (keys, canonical links, search pages)
4. `busca`, `materias/` (`api`, `html`, `valores`, `Fontes`), `autoria`
5. `tabela` (final table, extra columns, `Relevante`), `downloads`
6. `projeto` (paths of `<nome>_proj/`), `execucao` (`por_casa`: worker pool,
   Ctrl+C, progress line)
7. `interface/` (`entrada`: prompts; `principal`: menu, flows, `executar()`)

## Target system

- **SAPL** (Interlegis) instances, one per legislative house, list in
  `arquivos_csv/casas_legislativas.xlsx` (1 404 houses; about a third do not
  resolve in DNS).
- **Shared servers.** Almost every working house resolves to the same
  Interlegis address (`201.54.51.178`, a few to `.179`; DNS check on
  2026-10-27). The client therefore also limits each server (IP), summed over
  its houses.
- Endpoints used: `/sistema/search/?page=N&q=…`; the JSON API
  `/api/materia/materialegislativa/<id>/`, `/api/materia/autoria/?materia=<id>`,
  `/api/materia/tramitacao/?materia=<id>` and the name lookups
  (`tipomaterialegislativa`, `regimetramitacao`, `statustramitacao`,
  `unidadetramitacao`, `/api/base/autor/`, `/api/base/tipoautor/`); the HTML
  fallbacks `/materia/<id>`, `/materia/<id>/autoria`, `/materia/<id>/tramitacao`;
  and the PDF links (`/media/…`).
- Observed limit: 35 requests/min per site, then `HTTP 429` with
  `Retry-After: 60`. The client keeps 35 requests in a 60 s window plus a 1 s
  margin per site, and `limite_por_servidor` (default 120) per server in the
  same window; both shared across runs through `.sapl_historico.json`. 429s
  from two houses of one server within 10 min halve that server's ceiling for
  the rest of the run (floor 35).

## Planned (later specs)

Order as in the ROADMAP.

| Spec                         | Additions                                              |
|------------------------------|--------------------------------------------------------|
| SQL output and documents     | SQLite by default, PostgreSQL optional, via SQLAlchemy; documents in the project folder by hash, or MongoDB (GridFS) / S3-compatible storage (MinIO, S3) |
| Keyword suggestions          | NLTK RSLP stemmer, scikit-learn (TF-IDF); optional embeddings or an LLM API |
| Web UI                       | FastAPI or Flask + plain HTML/CSS/JS                   |
| Quality                      | Pinned versions (`requirements.lock`)                  |
| Search in results            | SQLite FTS5 / PostgreSQL `tsvector`; `pypdf` or `pdfminer.six`; optional OCR (Tesseract) |
| Config, CLI and cloud        | `argparse`, `config.yaml` (PyYAML); Docker; AWS (SQS, Lambda/Fargate, S3, RDS) |
