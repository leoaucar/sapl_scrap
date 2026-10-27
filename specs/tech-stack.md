# Tech stack — SAPyL (formerly sapl_scrap)

Current stack, and what is planned for later specs. Changing anything in
"Current" requires a note in the spec's plan.

## Current

| Area            | Choice                                   | Notes                                      |
|-----------------|------------------------------------------|--------------------------------------------|
| Language        | Python ≥ 3.10                            | Tested on 3.12                             |
| HTTP            | `requests` (+ `urllib3`, bundled)        | One shared `Session` per run               |
| HTML parsing    | `beautifulsoup4` with `html.parser`      | Explicit parser, no extra dependency       |
| Tables / output | `pandas` (≥ 2.1, works with 3.x), CSV    | `openpyxl` for reading `.xlsx` inputs      |
| Logging         | `logging` (standard library)             | Terminal + file per project                |
| Interface       | Interactive terminal (`input()`)         | Replaced by config/CLI in a later spec     |
| Tests           | `pytest` (dev dependency)                | Offline; fixtures under `tests/fixtures/`  |
| Coverage        | `pytest-cov` (dev dependency)            | Report only, no threshold                  |
| CI              | GitHub Actions                           | `pytest` on push/PR, Python 3.10 and 3.12  |
| Dependencies    | `requirements.txt` (+ `requirements-dev.txt`) |                                       |

## Target system

- **SAPL** (Interlegis) instances, one per legislative house, list in
  `arquivos_csv/casas_legislativas.xlsx` (~840 houses).
- Endpoints used: `/sistema/search/?page=N&q=…`, `/materia/<id>`,
  `/materia/<id>/autoria`, `/materia/<id>/tramitacao`, and the PDF links found
  on the matter page.
- Observed limit: 35 requests/min per site, then `HTTP 429` with
  `Retry-After: 60` (the search endpoint did not appear to be limited in the
  2026-10-15 test).

## Planned (later specs)

| Spec                         | Additions                                              |
|------------------------------|--------------------------------------------------------|
| Parallelism                  | `concurrent.futures.ThreadPoolExecutor`; maybe `httpx`/`asyncio` later |
| SQL output                   | SQLite by default, PostgreSQL optional, via SQLAlchemy |
| Config & CLI                 | `argparse`, `config.yaml` (PyYAML)                     |
| Cloud (later)                | Docker; AWS (SQS, Lambda/Fargate, S3, RDS)             |
| Web UI (later)               | FastAPI or Flask + plain HTML/CSS/JS                   |
