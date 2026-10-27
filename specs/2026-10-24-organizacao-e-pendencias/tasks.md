# Tasks: Code organization, SAPyL identity and leftover issues

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Status:** Approved 2026-10-27
- **Branch:** `spec/2026-10-24-organizacao-e-pendencias` (from `main`, after the
  runtime-improvements merge)

Rules for every task (same as Phase 1):
- A task is done when its tests are written, `pytest` passes with the
  network blocked, `ruff` passes (from T07 on) and CI is green on the branch.
- One commit per task, at most. Message in Portuguese, starting with the task
  id. No AI co-author trailers. Check pytest's own exit code before
  committing.
- Tests come with the code, in the same task.
- Tick the box here in the same commit.

## Phase A: Before moving anything

- [x] **T01 Branch and Phase 1 project fixture** (TR-4)
  - Create the branch from the updated `main`.
  - `tests/fixtures/gerar_projeto_fase1.py`: runs the **Phase 1** `programa.main`
    against `SaplFalso` (two houses, one matter failing) and copies the project
    folder to `tests/fixtures/projeto_fase1/`.
  - `tests/test_compat_fase1.py` (first version): the fixture has the expected
    files, and the Phase 1 code resumes it without requesting finished matters.
- [x] **T02 New API fixtures** (TR-2)
  - autoria, autor, tipoautor, tramitação, statustramitacao and
    unidadetramitacao for Cascavel and Rio Branco (≤ 15 requests per house,
    3 s apart). Remove `ip`/`user`, then update `index.json` and the
    fixtures README.
  - `test_fixtures.py` already checks for `ip`/`user`. Add the new files to
    its existence check.

## Phase B: Packaging and the move (no behaviour change)

- [x] **T03 `pyproject.toml` packaging and CI jobs** (FR-1, FR-6 config, TR-5, TR-6)
  - `[project]`, `[project.scripts]`, the `dev` extra, `[tool.ruff]`, and
    coverage of `sapyl`. Add `ruff` to the dev extra. `requirements*.txt`
    become wrappers.
  - CI: `testes` job (ruff steps allowed to fail until T07) and
    `instalacao` job.
  - Done when CI is green, with the ruff steps marked `continue-on-error`.
  - *As built:* the `sapyl/` folder doesn't exist yet, so coverage stays on
    `.` until T04, and the `instalacao` job only checks the installed
    version. Its `sapyl --version` / `python -m sapyl --version` steps are
    added in T06.
- [ ] **T04 Move modules into `sapyl/`** (FR-3, TR-1)
  - `git mv` every module to the plan §3 path (still the old module
    contents). Change imports to absolute and update the tests' imports only.
    Add `sapyl/__init__.py` with `__version__ = '0.2.0'`.
  - Done when the suite is green with **no assertion changed** and
    `test_compat_fase1` passes.
- [ ] **T05 Single source for columns and stages** (FR-4)
  - `sapyl/colunas.py`. Every module imports from it.
  - Test: no other module defines a list containing `'Link Materia'` or
    `'etapa'` (AST scan).
- [ ] **T06 Split matters, links and the interface** (FR-3, FR-2)
  - `materias/` subpackage, `links.py`, `interface/` (`entrada`,
    `principal`), `__main__.py`, the `executar()` entry point with
    `--version`, and the `programa.py` shortcut.
  - `test_instalacao.py`: `executar(['--version'])`, plus `python -m sapyl
    --version` and `python programa.py --version` via `subprocess`, without
    network access.
  - `test_camadas.py`: layer order from plan §3.
- [ ] **T07 Types, docstrings, ruff** (FR-5, FR-6)
  - Type hints and docstrings on public functions. `ruff format` goes in
    its own commit (T07a). Then `ruff check` is clean (T07b), and CI drops
    `continue-on-error`.

## Phase C: Data and identity

- [ ] **T08 Stop tracking generated and research data** (FR-8, FR-9, FR-10)
  - `git rm --cached` + `.gitignore` with comments.
  - Replace `palavras_chave_res.csv` with `exemplo_palavras_chave.csv`
    (plan §6) and add the README table.
  - Also create `exemplo_palavras_chave_educacao.csv` from the old list,
    cleaned (FR-10a, plan §6).
  - Tests: both example files have no BOM, have the `Palavras` column, and
    contain no double spaces. `preparar_termos` turns the neutral one into
    the queries shown in the README, and the education list into 23 queries
    with `"aparelhamento+ideologico"`.
  - Test: `git ls-files` (via `subprocess`) contains no file from a
    forbidden list. The test is skipped when not in a git checkout.
  - Check that a fresh clone without `casas_resultado.csv` doesn't offer
    to reuse a table (there's already a test for the prompt; add one for a
    missing file).
- [ ] **T09 SAPyL identity** (FR-11, FR-13)
  - README header and "Para que serve", the `User-Agent`, the welcome line
    and summary/log header, and the `AUTHORS.md` citation.
  - Tests: the `User-Agent` contains `SAPyL/0.2.0`, and the summary and the
    welcome line contain `SAPyL`.

## Phase D: Leftover issues

- [ ] **T10 SSL and DNS errors are not retried** (FR-24)
  - `test_cliente_http.py`: `SSLError` → `ssl`, 1 attempt. A
    `ConnectionError` caused by `NameResolutionError` → `dns`, 1 attempt. One
    caused by `socket.gaierror` → `dns`. A plain `ConnectionError` still gets
    4 attempts.
- [ ] **T11 One log per run** (FR-26)
  - `registro.configurar(pasta, nome, modo)` creates `logs/<nome>_<data_hora>_<modo>.log`.
  - Tests: name format, one file per run, summary shows the path, old
    `<nome>.log` untouched.
- [ ] **T12 Cache of sources and names** (FR-25)
  - `estado.Cache`. `Fontes`/`Consultas` use it.
  - Tests: a resume makes no API probe and no lookup for known names, a
    failed lookup is not cached, a corrupt file gives a warning and an empty
    cache, and saving is atomic (the temp file is gone).
- [ ] **T13 Keywords warning on resume** (FR-23)
  - Tests: the warning lists added and removed terms, the saved terms are
    used, and no warning appears when the terms are equal or the file is
    missing.
- [ ] **T14 Search file with links only** (FR-21, FR-22, NFR-3)
  - Tests: the page file has links but no HTML, an old raw file is still read
    on resume, both files together give the same deduplicated links, and the
    file for the Rio Branco fixture page is ≥ 10× smaller than its raw row.
- [ ] **T15 Houses that redirect** (FR-27)
  - Tests: a redirect gives `url_final`, requests go to `url_final`, links on
    either host are accepted, keys stay on the original host, and an old
    table without `url_final` still works.
- [ ] **T16 Update mode keeps the researcher's columns** (FR-19, FR-20)
  - Tests: extra columns are carried over by key and in order, the
    `Relevante` prompt appears only when the column exists, the accepted
    values are normalised, and the filter count is logged.
- [ ] **T17 Authors and procedure through the API** (FR-14, FR-15, FR-16)
  - `sapyl/autoria.py` gets API functions with cached lookups and the HTML
    fallback per house.
  - Tests: API path with the T02 fixtures, API≡HTML text for the same
    matter (TR-3), switch to HTML on 404/non-JSON, failures recorded.
- [ ] **T18 Authors and procedure in the menu, with resume** (FR-7, FR-17, FR-18)
  - Menu option 3. The input is a project name or a CSV path. Output and
    state go in the project folder or next to the CSV. Partial file and state
    as in plan §7.8. Remove `autoria_e_tramitacao/`.
  - Tests: project input picks the latest final, CSV input works, the input
    is not modified, Ctrl+C then resume fetches only what's missing, and the
    output has the input's columns plus the new ones.

## Phase E: Phase 1 findings, end-to-end, docs

- [ ] **T19 Phase 1 validation findings** (spec §9). Only V4 is open:
  - **T19.1 Safety margin in the rate window** (FR-29). One constant
    (`MARGEM_SEGUNDOS = 1`). Test: with the fake clock, request 36 goes
    ≥ 61 s after request 1. Update the existing limiter tests' expected
    times.
- [ ] **T20 End-to-end and compatibility** (TR-4, TR-7)
  - `test_ponta_a_ponta.py`: authors/procedure with interruption and resume,
    update with `Relevante` and the filter, a DNS-failing house, and ≤ 35
    requests/60 s per site including autoria.
  - `test_compat_fase1.py` (final version): the new code resumes and updates
    `projeto_fase1`.
- [ ] **T21 Docs** (NFR-4)
  - README (install, `sapyl`, menu, logs, update with `Relevante`, authors
    and procedure), tech-stack (package, ruff), CLAUDE.md (local),
    ROADMAP ticks.

## Phase F: Validation, merge, rename

- [ ] **T22 Update `validation.md`** to match what was built.
- [ ] **T23 Run validation**, record the results, fix what fails, then merge
  into `main`.
- [ ] **T24 Rename the repository on GitHub to `sapyl`** (FR-12), **only
  with the user's go-ahead at that moment**: `gh repo rename sapyl`,
  `git remote set-url`, and update the badge, clone URL and links on `main`.
  Check that the CI badge renders and that the old URL redirects.

## Traceability

| Requirement | Tasks | Tests |
|---|---|---|
| FR-1 | T03 | CI `instalacao`, `test_instalacao` |
| FR-2 | T06 | `test_instalacao` |
| FR-3 | T04, T06 | `test_camadas`, whole suite |
| FR-4 | T05 | `test_colunas` (AST scan) |
| FR-5 | T07 | review (no automated check) |
| FR-6 | T03, T07 | CI ruff steps |
| FR-7 | T18 | `test_principal`, `test_autoria` |
| FR-8, FR-9, FR-10, FR-10a | T08 | `test_repositorio`, `test_palavras` |
| FR-11 | T09 | review |
| FR-12 | T24 | manual check (validation) |
| FR-13 | T09 | `test_registro`, `test_principal` |
| FR-14, FR-15, FR-16 | T17 | `test_autoria` |
| FR-17, FR-18 | T18 | `test_autoria`, `test_ponta_a_ponta` |
| FR-19, FR-20 | T16 | `test_principal`, `test_ponta_a_ponta` |
| FR-21, FR-22 | T14 | `test_busca`, `test_links`, `test_compat_fase1` |
| FR-23 | T13 | `test_principal` |
| FR-24 | T10 | `test_cliente_http`, `test_ponta_a_ponta` |
| FR-25 | T12 | `test_estado`, `test_materias`, `test_autoria` |
| FR-26 | T11 | `test_registro` |
| FR-27 | T15 | `test_casas`, `test_links` |
| FR-28 | T19 | one test per finding |
| FR-29 | T19.1 | `test_cliente_http` |
| TR-1 | T04 | whole suite, coverage ≥ 95 % |
| TR-2 | T02 | `test_fixtures` |
| TR-3 | T17 | `test_autoria` |
| TR-4 | T01, T20 | `test_compat_fase1` |
| TR-5 | T03, T06 | CI `instalacao`, `test_instalacao` |
| TR-6 | T03, T07 | CI |
| TR-7 | T20 | `test_ponta_a_ponta` |
| NFR-3 | T14 | `test_busca` |
| NFR-4 | T21 | review |
