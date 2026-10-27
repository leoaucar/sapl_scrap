# Spec: Code organization, SAPyL identity and leftover issues

- **Status:** Approved 2026-10-27 · amended 2026-10-27 (project site, FR-13a, at the user's request)
- **Date:** 2026-10-24
- **Covers:** ROADMAP Phase 1b (organization, new identity, leftover bugs)
- **Depends on:** [2026-10-24-runtime-improvements](../2026-10-24-runtime-improvements/spec.md)
  merged into `main` after its validation
- **Principles:** [constitution](../constitution.md) · **Stack:** [tech-stack](../tech-stack.md)

## 1. Problem

The runtime-improvements spec made the scraper reliable, but on purpose it
kept a flat layout of 13 top-level modules. Some problems remain:

- **Hard to install and run.** There is no installable package and no
  command. The authors/procedure script lives in a separate folder and only
  works by editing `sys.path`.
- **Input and generated data are mixed.** The program rewrites
  `arquivos_csv/casas_resultado.csv`, which is tracked in git, and
  `autoria_e_tramitacao/tabela_limpa_2.csv` is research data in the
  repository.
- **No lint or format checks.** Style varies between old and new modules.
- **The project has no public identity.** It is still called `sapl_scrap`. It
  should present itself as an open-source tool for following many Brazilian
  legislative houses: **SAPyL: Raspador do Sistema de Apoio Legislativo**.
- **Issues left over from Phase 1:**
  - the authors/procedure script cannot resume (it writes only at the end)
    and still parses HTML when the API exists;
  - update mode drops the columns a researcher added by hand (e.g.
    `Relevante`);
  - the raw search file stores whole HTML pages (~1 GB for a full run);
  - a resumed project silently ignores an edited keywords file;
  - permanent errors (SSL certificate, DNS) are retried as if temporary;
  - every resume probes each house's API and repeats the name lookups again;
  - the project log grows without limit across resumes;
  - houses whose site redirects to another domain may lose matter links.
- Plus whatever the Phase 1 validation finds (§9).

## 2. Goals

1. A researcher installs with `pip install .` and runs one command, `sapyl`.
   Everything, including authors/procedure, is reachable from it.
2. The code is a package with clear layers and consistent names. Lint and
   format checks run in CI.
3. Git holds code, docs, test fixtures and example inputs only. Generated and
   research data stay on the researcher's disk.
4. README, package, command, repository and messages use the SAPyL name.
5. Every leftover issue listed in §1 is fixed and tested.
6. Projects created with the Phase 1 version keep working (resume and update).

## 3. Non-goals

- Parallelism, SQL output, config file / command-line options (later
  specs). The `sapyl` command stays interactive. Command-line arguments come
  with the config & CLI spec.
- A logo or other images (identity is text-only, by decision).
- Rewriting git history (removed data stays in old commits).
- New data fields in the matters table.

## 4. Users and scenarios

- **S1. New install.** A researcher clones the repository, runs
  `pip install .`, then `sapyl`. The same menu as today appears, with one
  more option for authors and procedure.
- **S2. Old project.** A project created with the Phase 1 version is resumed
  or updated with the new version, without errors and without redoing
  finished work.
- **S3. Filtered update.** The researcher adds a `Relevante` column to the
  final CSV, marks some rows, and runs the update keeping only the relevant
  ones. The new file still has the `Relevante` column and any other columns
  they added.
- **S4. Authors and procedure for a project.** From the menu, the researcher
  picks a project (or a CSV). Authors and the latest procedure step are
  fetched through the API, with HTML as fallback. If interrupted, it resumes.
- **S5. Keywords changed.** The researcher edits the keywords file and
  resumes an old project. The program says the project keeps its original
  keywords and explains how to search the new ones (a new project).
- **S6. Broken house.** A house's domain no longer exists, or its
  certificate is invalid. It is marked as failed quickly, after one attempt,
  with reason `dns` or `ssl`.

## 5. Functional requirements

### 5.1 Package, command and layout

- **FR-1** The code is a Python package `sapyl` with `pyproject.toml` as the
  single source of metadata and dependencies (runtime + `dev` extra).
  `requirements.txt` and `requirements-dev.txt` stay as thin wrappers for
  people who already use them.
- **FR-2** `pip install .` installs a `sapyl` command. `python -m sapyl` does
  the same. `programa.py` stays at the root as a shortcut that calls the
  package.
- **FR-3** Layers, one module or subpackage each: HTTP client · houses ·
  search · links · matters (API, HTML, shared columns) · downloads · project
  and state · authors/procedure · interface (prompts and main flow) · log
  and summary. Each layer depends only on the layers below it (interface on
  top, HTTP at the bottom).
- **FR-4** The final table's columns, the links columns and the state stages
  are each defined in one place. No module repeats those lists.
- **FR-5** Public functions have type hints and docstrings. Names follow one
  convention (Portuguese, `snake_case`, verbs for functions).
- **FR-6** `ruff check` and `ruff format --check` pass and run in CI. The
  `ruff` settings live in `pyproject.toml`.
- **FR-7** The main menu gets an option *"Autoria e tramitação"* (§5.4). The
  separate `autoria_e_tramitacao/` folder is removed.

### 5.2 Data in the repository

- **FR-8** `arquivos_csv/casas_resultado.csv` (the shared table of tested
  houses, rewritten by the program) is no longer tracked and is gitignored.
  On a fresh clone, the program behaves as it does today when the file is
  missing: it doesn't offer to reuse a table.
- **FR-9** `autoria_e_tramitacao/tabela_limpa_2.csv` is no longer tracked.
  The file stays on the researcher's disk, moved by hand or left where it is.
- **FR-10** Example inputs stay tracked: `arquivos_csv/casas_legislativas.xlsx`
  and `arquivos_csv/palavras_chave.xlsx`. `arquivos_csv/palavras_chave_res.csv`
  (an unused CSV copy of a research list, with a BOM, a typo and double
  spaces) is replaced by `arquivos_csv/exemplo_palavras_chave.csv`. It's a
  short, neutral, clean UTF-8 example showing each format: a single word, an
  exact phrase, terms combined with a comma, and spelling variants as
  separate lines. The README explains each line and the query it becomes
  (Q1).
- **FR-10a** The old research list is kept, cleaned, as an alternative and
  larger test: `arquivos_csv/exemplo_palavras_chave_educacao.csv` (23 lines
  on education, gender and ideology). Cleaning means removing the BOM,
  fixing the typo "aparellhamento" and collapsing the double spaces after
  commas. The terms and variants themselves are unchanged.

### 5.3 Identity

- **FR-11** README opens with the name *SAPyL: Raspador do Sistema de Apoio
  Legislativo*, a one-line tagline and a short description of the
  purpose: an open-source tool to follow what is happening in many
  Brazilian legislative houses at once. Badges stay. No images.
- **FR-12** The repository is renamed on GitHub to `sapyl`, and every link
  is updated: badge, clone URL, HTTP `User-Agent`, citation in `AUTHORS.md`,
  CLAUDE/README references. The rename happens after this spec is merged
  (GitHub redirects old URLs).
- **FR-13** User-facing messages that name the program (welcome line,
  summary, log header) say SAPyL.
- **FR-13a** A project site on GitHub Pages, in Portuguese, for people who
  won't read the README: one static page (`docs/index.html`, HTML + CSS, no
  scripts, no images, no external fonts or files). It explains what SAPyL is
  and who it is for, what it produces, the requirements, installation
  (clone + `pip install .`) and use (the `sapyl` command and its menu: new
  or resumed project, update, authors and procedure; input files; outputs;
  resuming; the 35 requests/min limit and what it means for run time),
  plus citation, license and links to the repository and README. It is
  readable on a phone and in light and dark mode. A GitHub Actions workflow
  publishes `docs/` from `main`. Pages is switched on after the rename
  (FR-12), because GitHub does not redirect Pages addresses of renamed
  repositories, so the site lives at `https://leoaucar.github.io/sapyl/`.
  The README links to it.

### 5.4 Authors and procedure

- **FR-14** Authors come from `/api/materia/autoria/?materia=<id>`, with
  author names from `/api/base/autor/<id>/` and author types from
  `/api/base/tipoautor/<id>/`. The HTML `/autoria` page is the fallback for
  houses without an API (same source choice as for matters, per house).
- **FR-15** The latest procedure step comes from
  `/api/materia/tramitacao/?materia=<id>` (newest first). Status and unit
  names come from `/api/materia/statustramitacao/<id>/` and
  `/api/materia/unidadetramitacao/<id>/`. The HTML `/tramitacao` page is the
  fallback.
- **FR-16** API and HTML produce the same text: `Autoria` =
  `"NOME (Tipo); …"` and `Tramite` =
  `"dd/mm/aaaa | unidade local | unidade destino | status"`.
- **FR-17** It works on a project (its final CSV) or on any CSV with a
  `Link Materia` column, and writes `<entrada>_autoria_tramitacao.csv`. The
  input is never modified.
- **FR-18** It records progress like the main flow (state file, rows written
  as they finish). An interrupted run resumes and fetches only what is
  missing or failed.

### 5.5 Update mode

- **FR-19** Columns of the input final CSV that are not program columns
  (e.g. `Relevante`, notes) are carried over, by matter key, to the
  `_ATUALIZADO_` file, after the program columns.
- **FR-20** If the input has a `Relevante` column, the program asks whether
  to update only the relevant rows. Values `sim`, `s`, `x`, `1`, `true`
  count as relevant, case-insensitive, ignoring surrounding spaces.

### 5.6 Search output

- **FR-21** The search stage stores, for each results page, only the matter
  links found (plus house, keyword, page and URL), not the HTML. The new
  file is `<nome>_paginas_busca.csv`.
- **FR-22** Projects that have the old `<nome>_resultados_crus_casas.csv`
  still resume: links are read from it, and new pages go to the new file.

### 5.7 Robustness leftovers

- **FR-23** When a project is resumed and the current keywords file differs
  from the keywords saved in `config.json`, the program warns. It lists the
  difference and keeps the saved keywords. Searching new keywords means
  creating a new project.
- **FR-24** SSL certificate errors and DNS failures (the name does not
  resolve) are not retried. The reason is `ssl` or `dns`. Other connection
  errors keep the current retries.
- **FR-25** The source chosen for each house (`api`/`html`) and the names
  looked up (types, regimes, statuses, units, authors) are saved in the
  project. A resume reuses them instead of asking the sites again.
- **FR-26** Each run (new, resume, update, authors) writes its own log file
  in `<nome>_proj/logs/` named by date and time. The summary shows its path.
  The Phase 1 `<nome>.log` of old projects is left untouched.
- **FR-27** When the availability test sees a house's site redirect to
  another address, the final address is recorded (`url_final` in the house
  table) and used for every request to that house. Links on either domain
  count as the same house.

### 5.8 Validation findings

- **FR-28** Each issue in the "Issues found" table of the Phase 1
  `validation.md` that is not fixed before that merge becomes a requirement
  here (§9), with its own tests.

## 6. Testing

Tests ship with the code (constitution §4), offline, with the existing
helpers (`SessaoFalsa`, `RelogioFalso`, `SaplFalso`, `roteiro`).

- **TR-1** The test suite moves along with the package (`tests/` tests
  `sapyl.*`). No behaviour test from Phase 1 is deleted without a
  replacement. Coverage stays at or above Phase 1 level (≥ 95 %).
- **TR-2** New fixtures (real responses, saved like the Phase 1 ones, staff
  data removed): API autoria, autor, tipoautor, tramitação, statustramitacao
  and unidadetramitacao for at least two houses. HTML autoria/tramitação
  already exist.
- **TR-3** Equivalence tests: for the same matter, API and HTML give the same
  `Autoria` and `Tramite` text.
- **TR-4** Compatibility tests with a project folder made by the Phase 1
  version (stored as a small fixture). It must resume and update, read the
  old raw file and the old `<nome>.log` name, and skip finished work.
- **TR-5** Install test in CI: `pip install .` in a clean environment, then
  `sapyl --version` and `python -m sapyl --version` succeed. `--version` is
  the only command-line option added in this spec.
- **TR-6** CI runs `ruff check`, `ruff format --check` and `pytest` on
  Python 3.10 and 3.12.
- **TR-8** `test_site.py` checks `docs/index.html`: it parses, has a title
  and the required sections (FR-13a), shows `pip install .` and `sapyl`,
  loads nothing from outside `docs/`, and names no removed file or command
  (`autoria_e_tramit.py`, `palavras_chave_res.csv`, `sapl_scrap` outside
  the citation of old versions).
- **TR-7** The end-to-end test from Phase 1 is extended. It runs the
  authors/procedure option with interruption and resume, an update with
  `Relevante` and a filter, and a house with a DNS failure. It also checks
  that no site gets more than 35 requests in any 60 s, including the
  authors/procedure requests.

## 7. Non-functional requirements

- **NFR-1 Compatibility.** Input files and their columns are unchanged. The
  final table's columns are unchanged. Phase 1 projects keep working (TR-4).
- **NFR-2 Dependencies.** `ruff` is added as a dev dependency. No new runtime
  dependency.
- **NFR-3 Size.** The search file for the 10-house Acre test is at least
  10× smaller than the Phase 1 raw file for the same run.
- **NFR-4 Docs.** README (install with `pip install .`, the `sapyl` command,
  authors/procedure in the menu, logs folder, update with `Relevante`),
  tech-stack (package layout, ruff), CLAUDE.md, ROADMAP ticks. The project
  site (FR-13a) says the same as the README about installing and using.

## 8. Acceptance criteria

1. In a fresh virtual environment, `pip install .` then `sapyl` opens the
   menu, and `python -m sapyl` and `python programa.py` do too.
2. `ruff check`, `ruff format --check` and `pytest` pass locally and in CI
   (3.10 and 3.12). Coverage ≥ 95 %.
3. `git ls-files` lists no generated or research data (FR-8, FR-9).
4. The Phase 1 validation project `val_a` resumes and updates with the new
   version without redoing finished work.
5. Authors/procedure on a real project uses the API (and HTML for a house
   without API), survives Ctrl+C + resume, and stays within 35 requests/min
   per site.
6. An update with a `Relevante` column keeps that column and, when asked,
   updates only the relevant rows.
7. The search file of a new 10-house run is ≥ 10× smaller than Phase 1's raw
   file for the same run.
8. A house with a non-existent domain fails after a single attempt with
   reason `dns`.
9. The repository is `leoaucar/sapyl` on GitHub, and README, badge, clone
   URL and citation use the new name.
10. The project site opens at `https://leoaucar.github.io/sapyl/`, and its
    installation steps work as written in a fresh virtual environment.

## 9. Validation findings from Phase 1

From `../2026-10-24-runtime-improvements/validation.md` ("Issues found"),
run on 2026-10-24/25:

- **V1, V2, V3, V5 (fixed in Phase 1, before its merge):** send time in the
  log; the rate limit now holds across runs (history on disk); an isolated
  API 404 no longer switches a whole house to HTML; Ctrl+D at a prompt no
  longer crashes. Their tests move with the package (TR-1).
- **V4 (open):** the limiter lets request 36 go exactly 60.000 s after
  request 1. Network jitter could make the server see them less than 60 s
  apart.
  - **FR-29** The window gets a safety margin (default 1 s, one constant),
    so consecutive requests 1 and 36 to a site are always ≥ 61 s apart when
    sent. Tests use the fake clock.
- **Observed, for FR-16:** many matters have no procedure record at all (the
  HTML page says "Nenhum registro encontrado"; 51 % of `Tramite` empty in run
  E). That is correct: `Tramite` stays empty with status `ok`. The API path
  must behave the same (empty list → empty `Tramite`, `ok`).
- **Observed, for FR-24's validation:** `sapl.marata.rs.leg.br` is listed as
  active in the old shared table, but its name no longer resolves.

## 10. Decisions

- **Q1.** `palavras_chave_res.csv` is replaced by a neutral, documented
  example (FR-10), and the old list is kept, cleaned, as an alternative test
  (FR-10a). *Decided 2026-10-24.*
- **Q2.** Authors/procedure stays a separate menu option, not a question in
  the main flow (FR-7). *Decided 2026-10-24.*
- **Q3.** The project site goes into this spec (it uses this spec's name and
  install steps) as one hand-written static page in `docs/`, published by a
  GitHub Actions workflow (FR-13a). *Decided 2026-10-27.*

## 11. Open questions

None.
