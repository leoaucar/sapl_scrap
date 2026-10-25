# Spec: Runtime improvements

- **Status:** Approved
- **Date:** 2026-10-24
- **Covers:** ROADMAP §3 bugs 1–12 and §4 "Prioridade máxima" + Phase 1
  (except SQL, parallelism and config/CLI, which are later specs)
- **Principles:** [constitution](../constitution.md) · **Stack:** [tech-stack](../tech-stack.md)

## 1. Problem

In the 2026-10-15 test (10 houses from Acre, 3 keywords), **87% of the matters
(1131 of 1306) came back empty**. SAPL sites allow 35 requests per minute per
site and then answer `HTTP 429`. The scraper never checks the response status,
so it records the error page as a matter with no data, and the run looks
successful.

Besides that, the program:
- reads fields that no longer exist on SAPL pages (`Data`, `Assuntos` and
  `texto_integral` are always empty);
- scrapes and downloads the same matter several times when more than one
  keyword finds it;
- can hang forever (no timeout, infinite retry in the search);
- crashes on invalid input or when a folder already exists;
- drops failures silently (houses that did not answer, failed downloads);
- cannot resume: an interrupted run must start over, which is not viable for
  a full run (estimated 10–20 h sequentially).

## 2. Goals

1. A run either gets a matter's data or records that it failed, and why.
2. The program stays within each site's request limit.
3. Every field in the output is either filled from the page or legitimately
   empty on that page.
4. Each matter is scraped and downloaded once per run.
5. A run can be interrupted and resumed without repeating finished work.
6. The program does not hang or crash on bad input, existing folders or
   network problems.
7. All of the above is covered by offline automated tests, including an
   end-to-end run against a fake SAPL.

## 3. Non-goals (later specs)

- Running several houses in parallel (spec: parallelism).
- SQL database output (spec: SQL output).
- Config file / command-line arguments; the interactive prompts stay
  (spec: config & CLI).
- Changing which links count as "matters" (sessions, norms — see TODO in
  `raspador.py`).
- Removing the raw search HTML file (belongs with the parallelism spec).

## 4. Users and scenarios

**Researcher (main user)** — runs `python programa.py`, answers the prompts,
opens `<nome>_resultado_final.csv` in a spreadsheet.

- **S1. Full, trustworthy run.** The researcher runs the 10-house test. The
  run takes longer than before (it now waits for the rate limit), shows
  progress, and ends with a summary: matters found, scraped OK, failed, PDFs
  downloaded. No matter is silently empty.
- **S2. Interrupted run.** The run is stopped (Ctrl+C, power loss, network
  down) halfway through scraping. The researcher starts the program again,
  picks the same project, and it continues from where it stopped.
- **S3. Failures to retry.** Some matters failed (site down for an hour).
  Resuming the project retries only the failed and missing ones.
- **S4. Update mode.** The researcher filtered `_resultado_final.csv` and
  re-scrapes it with the existing "update" option; it gets the same
  protections (rate limit, status, no duplicates).
- **S5. Authors and procedure.** The researcher runs `autoria_e_tramit.py` on
  a results file; it respects the rate limit and records failures the same
  way.

## 5. Functional requirements

### 5.1 HTTP behaviour (all modules that access SAPL)

- **FR-1** All requests go through one shared HTTP layer with a connect/read
  timeout. No module calls `requests.get` directly.
- **FR-2** Requests to the same site are limited to **35 per minute** by
  default. The limit is a single constant that is easy to change.
- **FR-3** On `HTTP 429` the program waits for `Retry-After` (default 60 s if
  absent) and tries again.
- **FR-4** On network errors, timeouts and `5xx`, the program retries with
  increasing waits, up to a maximum number of attempts (default 3).
- **FR-5** After the last attempt the request is reported as failed with a
  reason (status code or error type). It never loops forever.
- **FR-6** The URL-availability test (`teste_url_ativa`) keeps houses that
  raised an error in its result, marked as inactive with the reason, instead
  of dropping them.

### 5.2 Search

- **FR-7** Pagination ends only on the "no more pages" answer (`404`).
  Any other non-200 status goes through FR-3/FR-4; if it still fails, the
  search for that house + keyword is recorded as incomplete and appears in
  the final summary.

### 5.3 Matter scraping

- **FR-8** A matter page is parsed only if the request succeeded (`200`).
- **FR-9** Every row in the matters table and in the final result has:
  - `status`: `ok` or `erro`
  - `erro`: empty, or the failure reason (e.g. `HTTP 429`, `timeout`)
  - `raspada_em`: date/time of the attempt
- **FR-10** Matter data comes from the SAPL JSON API
  (`/api/materia/materialegislativa/<id>`) when the house has it, and from
  the HTML matter page otherwise (older SAPL versions). Both sources produce
  the same columns; a `fonte` column says which one was used (`api` /
  `html`).
- **FR-10a** Output fields:
  - kept: `Titulo`, `Ementa`, `Ano`, `Data` (presentation date, now filled),
    `Numero`, `Observacao`, `Tipo de Materia Legislativa`, `texto_original`;
  - removed: `Assuntos` and `texto_integral` (not present on current pages;
    the "Assunto" subpage exists but was empty in all houses inspected);
  - added: `Indexacao`, `Em Tramitacao`, `Regime Tramitacao`,
    `Materia Anexada`, `Resultado`, `Data Publicacao`, `Numero Protocolo`,
    `Ultima Atualizacao` (API only; empty with the HTML source), `sapl_id`.
- **FR-10b** Personal data of house staff present in the API (`ip`, `user`)
  is never stored.
- **FR-11** BeautifulSoup is always called with an explicit parser.

### 5.4 Duplicates

- **FR-12** Each matter is identified by **house URL + SAPL id** (the number
  in `/materia/<id>`). Links are normalised (e.g. `/ta` suffix, trailing
  slashes) before comparison.
- **FR-13** Before scraping, duplicate links are merged into one row. The
  `Palavras` column lists **all** keywords that found that matter
  (separated by `; `).
- **FR-14** Each matter's PDF is downloaded at most once per run.

### 5.5 Downloads

- **FR-15** PDFs are saved with a stable name built from the house and the
  SAPL id (e.g. `<host-da-casa>_<sapl_id>.pdf`). The final result has a
  column with the file name, empty when there was no PDF.
- **FR-16** Downloads have a timeout, go through the shared HTTP layer, and
  are written straight to the destination folder (streamed, not held in
  memory).
- **FR-17** A failed download is recorded (column `download_status`:
  `ok` / `erro` / `sem_pdf`) and counted in the summary. Partial files are
  not left behind.

### 5.6 Resume

- **FR-18** Progress is saved to disk as the run goes in a per-project state
  file (`<nome>_proj/<nome>_estado.csv`, appended to as work completes),
  so an interruption loses at most the item in progress. It records:
  - each search (house + keyword) and whether it completed;
  - each matter (house + SAPL id) with its status and reason;
  - each PDF with its download status.

  The project CSVs are rebuilt from this state. The SQL spec will later
  replace this file.
- **FR-19** When the user gives the name of an existing project, the program
  offers to **resume** it instead of crashing. Resuming:
  - does not redo the search if it completed;
  - skips matters with `status = ok`;
  - retries matters with `status = erro` and those never attempted;
  - skips PDFs already downloaded (file exists and is complete).
- **FR-20** Starting a new project with a name that already exists never
  overwrites it; the user is asked to resume or choose another name.

### 5.7 Robust prompts and inputs

- **FR-21** Every numeric prompt validates its input and asks again on
  invalid answers (no `int(input())` crash). Menus accept only their listed
  options (the limit menu no longer accepts `5`).
- **FR-22** The Sul/Sudeste restriction is applied also when the house table
  is reused.
- **FR-23** "50 últimas casas" selects 50 houses.
- **FR-24** Creating a folder that already exists does not crash (the
  `downloads<data>` folder in update mode, for example).

### 5.8 Observability

- **FR-25** Progress and errors are logged with `logging` to the terminal
  and to `<nome>_proj/<nome>.log`.
- **FR-25a** Every HTTP request is logged (at debug level, in the file) with
  timestamp, host, URL, status and attempt number, so the rate limit can be
  checked after a run.
- **FR-26** Every run ends with a summary: houses searched / failed,
  searches incomplete, matters found / unique / ok / failed, PDFs ok /
  failed / without PDF, and the path of the final result. If there were
  failures, the summary says how to retry them (resume the project).

### 5.9 Authors and procedure script

- **FR-27** `autoria_e_tramit.py` uses the shared HTTP layer (FR-1 to FR-5).
- **FR-28** It asks for the input file at the prompt (listing the CSVs in
  the folder) instead of using "the first CSV in the folder", and writes to
  a new file instead of overwriting the input. Command-line arguments come
  with the config & CLI spec.
- **FR-29** `Tramite` is written as text, not as a Python list.
  Failures are recorded in status columns, like FR-9.

### 5.10 Clean-up

- **FR-30** Remove the unused and broken `teste_conteudo_atualizado` and the
  unused helpers in `gerenciador_projetos.py`. The manual `testes.py` is
  replaced by the automated test suite.

## 6. Testing

Tests are part of this spec's deliverable, not a follow-up (constitution §4).

### 6.1 Testability requirements (code changes that make testing possible)

- **TR-1** `programa.py` no longer runs on import: the flow moves into a
  `main()` called under `if __name__ == '__main__':`, and each stage (search,
  link extraction, scraping, treatment, downloads) is a function that can be
  called on its own with explicit inputs and output paths.
- **TR-2** The HTTP layer accepts its dependencies from outside: the
  underlying session, the clock and the sleep function. Tests use a fake
  clock, so waits of 60 s run instantly.
- **TR-3** Prompts go through small helper functions that accept an
  injectable input function, so menus and validation can be tested without a
  terminal.
- **TR-4** Paths (input folder, project folder) are parameters, not hard-coded
  `./arquivos_csv/` strings inside functions, so tests run in `tmp_path`.

### 6.2 Test suite

- **TR-5 Layout.** `tests/` with one test module per source module,
  `tests/conftest.py` with shared fixtures, and `tests/fixtures/` with saved
  pages. Run with `pytest` from the repo root; configured in
  `pyproject.toml` (or `pytest.ini`).
- **TR-6 Offline by default.** A fixture blocks real network access: any
  test that tries to open a real connection fails. Only `pytest` is added
  and `pytest-cov`
  (dev dependencies); HTTP is faked with a small fake session, not an extra
  mocking library.
- **TR-7 Fixtures from real pages.** Saved HTML from real SAPL sites
  (gathered during planning, Q2), covering at least:
  - a search results page with matter links, an empty results page, and the
    end of pagination (404);
  - matter pages from 2–3 houses / SAPL versions, including one with and one
    without a presentation date and one without a PDF;
  - a 429 response with `Retry-After`;
  - `autoria` and `tramitacao` pages.

  Each fixture records its source URL and fetch date in a comment or an
  index file.
- **TR-8 Speed.** The full suite runs in under 30 s and needs no setup
  beyond `pip install -r requirements-dev.txt`.

### 6.3 Required test cases

| Area | Cases (at least) |
|---|---|
| Rate limiter (FR-2) | 35 requests in a window go through; the 36th waits until the window frees; limits are independent per host; the limit constant is respected when changed |
| Retry (FR-3–FR-5) | 429 with `Retry-After` waits that long and retries; 429 without the header waits 60 s; timeout / connection error / 5xx retried with growing waits; gives up after the maximum attempts with the right reason; 404 and other 4xx are not retried |
| Availability test (FR-6) | an exception keeps the house as inactive with a reason |
| Search (FR-7) | paginates until 404; a persistent 429/500 marks the search incomplete instead of ending silently; empty results page |
| Link extraction | matter links kept; pagination, media and accessory-document links excluded; relative links joined to the house URL correctly |
| Field extraction (FR-8, FR-10, FR-11) | every output field from each saved matter page, with exact expected values; missing fields give `''`; labels are stripped (`Ementa\n\n`…) |
| Status (FR-9) | a failed request gives `status = erro` and a reason and is never parsed |
| Duplicates (FR-12–FR-14) | link normalisation (`/ta`, trailing slash, absolute vs relative); merging keeps one row and joins all keywords; same SAPL id in different houses are not merged |
| Downloads (FR-15–FR-17) | stable file name; streamed write; failure removes the partial file and records `erro`; no link gives `sem_pdf`; same matter downloaded once |
| Resume (FR-18–FR-20) | state file written as work completes; resuming skips `ok`, retries `erro` and unattempted; completed searches not repeated; interrupted mid-run (simulated exception) then resumed gives the same result as an uninterrupted run, except for timestamps; existing project never overwritten |
| Prompts (FR-21–FR-24) | invalid, empty and out-of-range answers are asked again; `5` rejected in the limit menu; Sul/Sudeste filter applied with a reused table; "50 últimas" gives 50; existing folder does not crash |
| Logs and summary (FR-25–FR-26) | one log line per request with host, status and attempt; summary counts match a known scenario |
| Autoria / tramitação (FR-27–FR-29) | chosen file is read, output written to a new file; `Tramite` is text; failures recorded |
| Treatment | column names and order of the final CSV, including new columns at the end (NFR-2); update mode with absolute `texto_original` links |

### 6.4 End-to-end test

- **TR-9** One test runs the whole pipeline (search → links → matters →
  final CSV → downloads) against a **fake SAPL**: a fake session that serves
  the saved fixtures for two houses, returns a 429 on some requests and
  fails one matter for good. It checks the final CSV, the state file, the
  downloaded files and the summary, then resumes and checks that only the
  failed matter is requested again.

### 6.5 Traceability

- **TR-10** `tasks.md` lists, for every FR, the test(s) that cover it. An FR
  with no test is either justified in `tasks.md` or the spec is not done.

### 6.6 Continuous integration

- **TR-11** A GitHub Actions workflow (`.github/workflows/tests.yml`) runs
  `pytest` with coverage report on every push and pull request, on Python
  3.10 and 3.12. It needs no secrets and never accesses SAPL sites
  (TR-6). The README shows the workflow's status badge.

### 6.7 Real-network validation (not part of the suite)

- Checks against the real SAPL sites (acceptance criteria 1–5) are
  described step by step in `validation.md` and run by hand, once, at the
  end of the spec. They are never run by `pytest`.

## 7. Non-functional requirements
- **NFR-1 Tests.** See §6.
- **NFR-2 Compatibility.** Existing input files (`palavras_chave.xlsx/.csv`,
  `casas_legislativas.xlsx`, `casas_resultado.csv`) keep working. The final
  CSV keeps its current columns (except those removed under FR-10) and adds
  the new ones at the end.
- **NFR-3 Performance.** Scraping one house costs about
  `nº de matérias ÷ 35` minutes. This is expected; speed comes in the
  parallelism spec. The rate limiter must not add noticeable waiting beyond
  the limit itself. The limit also applies to the search endpoint (Q3), so
  large houses search more slowly (Rio Branco: ~392 pages, from ~2 min to
  ~11 min).
- **NFR-4 Dependencies.** No new runtime dependency. `pytest` is added as a
  development dependency.
- **NFR-5 Docs.** README updated: new columns, resume, log file, summary,
  how to run the tests, removal of the "known problem" warning. ROADMAP
  checkboxes ticked.

## 8. Acceptance criteria

1. The 10-house Acre test (same keywords as 2026-10-15) ends with
   **0 rows that are both empty and `status = ok`**; every failure has
   `status = erro` and a reason.
2. During that run, no site receives more than 35 requests in any 60-second
   window (checked in the log).
3. `Data` is filled for matters whose page shows a presentation date.
4. No two rows in the final result share house + SAPL id; `Palavras` lists
   every keyword that found the matter.
5. Stopping the run during scraping and resuming it finishes the project
   without re-requesting matters already `ok` (checked in the log), and the
   final result equals that of an uninterrupted run, except for timestamps.
6. Invalid answers at every prompt are rejected without a crash; an
   existing project name leads to the resume / other-name choice.
7. `pytest` passes offline in under 30 s, with network access blocked, and
   every case in §6.3 plus the end-to-end test (§6.4) is present.
8. Every FR maps to at least one test in `tasks.md` (§6.5).
9. The GitHub Actions workflow passes on Python 3.10 and 3.12 (TR-11).

## 9. Decisions

- **Q1. Resume storage:** a state CSV per project (FR-18). *Decided 2026-10-24.*
- **Q2. Fields and source:** after inspecting 6 matters from 3 houses
  (Rio Branco, ALEAC, Cascavel), `Assuntos` and `texto_integral` are
  dropped, 8 fields are added, and the JSON API is the primary source with
  HTML as fallback (FR-10, FR-10a). *Decided 2026-10-24.*
- **Q4. PDFs and the rate limit:** PDFs are served by the same host under
  `/media/`, so downloads count toward the 35/min limit. *Confirmed
  2026-10-24.*
- **Q3. Search endpoint:** the 35/min limit applies there too (NFR-3).
  *Decided 2026-10-24.*
- **Q7. Coverage:** `pytest-cov` (dev dependency) reports line coverage on
  every run, with no minimum threshold; the case list (§6.3) and
  traceability (§6.5) are the gate. *Decided 2026-10-24.*
- **Q6. Continuous integration:** GitHub Actions, in this spec (TR-11).
  *Decided 2026-10-24.*
- **Q5. Update mode:** same behaviour as new projects (rate limit, status,
  dedup, resume, stable PDF names). *Decided 2026-10-24.*

## 10. Open questions

None.
