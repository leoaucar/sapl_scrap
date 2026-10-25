# Tasks: Runtime improvements

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Status:** Approved
- **Branch:** `spec/2026-10-24-runtime-improvements` (from `main`)

Rules for every task:
- A task is done when its tests are written, `pytest` passes locally with the
  network blocked, and CI is green on the branch.
- One commit per task (or less), message in Portuguese, starting with the
  task id (e.g. `T05: limitador por host`). No AI co-author trailers.
- Tests come with the code in the same task, never in a later one.
- Tick the box here in the same commit.

## Phase A — Foundations

- [x] **T01 Branch and test scaffolding**
  - Create branch `spec/2026-10-24-runtime-improvements`.
  - `pyproject.toml` with `[tool.pytest.ini_options]` and
    `[tool.coverage.run]` (plan §8.1).
  - `tests/__init__.py` (empty), `tests/conftest.py` with `bloquear_rede`
    (autouse), `RelogioFalso`, `SessaoFalsa`, `fixture()`, `projeto_tmp`.
  - `tests/test_conftest.py`: the network block fails a real connection;
    `SessaoFalsa` replays scripted responses and records requests;
    `RelogioFalso.dormir` advances time without waiting.
  - Done when: `pytest` runs, 0 network access, < 5 s.

- [x] **T02 CI workflow** — TR-11
  - `.github/workflows/tests.yml` (push + pull_request, Python 3.10 / 3.12,
    `pip install -r requirements-dev.txt`, `pytest`).
  - README badge.
  - Done when: workflow green on the branch for both versions.

- [x] **T03 Fixture documentation and synthetic fixtures** — TR-7
  - `tests/fixtures/README.md`: what each file is, source URL/date (from
    `index.json`), and how the synthetic ones were derived.
  - Synthetic, derived from real pages: `materia_sem_data.html`,
    `materia_sem_pdf.html`; a fake HTML-only house (search page + matter
    page, API answers 404).
  - `tests/test_fixtures.py`: every file listed in `index.json` exists; no
    API fixture contains a non-empty `ip` or `user`.

## Phase B — HTTP and logging

- [x] **T04 Logging setup** — FR-25
  - `registro.py`: `configurar(pasta, nome)` → terminal `INFO`, file
    `<nome>.log` `DEBUG`; idempotent (calling twice adds no handlers).
  - `tests/test_registro.py`: both handlers, levels, file created, no
    duplicate handlers.

- [x] **T05 HTTP client: limiter** — FR-1, FR-2, TR-2
  - `http_sapl.py`: `ClienteSAPL`, `Resposta`, `LIMITE_POR_MINUTO`,
    sliding window per host with injected clock/sleep.
  - `tests/test_http_sapl.py`: 35 requests pass without sleeping; the 36th
    sleeps until the oldest is 60 s old; two hosts don't affect each other;
    changing the constant changes the behaviour; default timeouts passed to
    the session.

- [x] **T06 HTTP client: retries and failures** — FR-3, FR-4, FR-5, FR-25a
  - 429 + `Retry-After` (seconds), default 60, cap 300, host-wide block;
    5xx/timeout/connection backoff 5/15/45 s; `max_tentativas`; reasons
    `HTTP <n>` / `timeout` / `conexao`; 404 and 4xx not retried; DEBUG line
    per attempt.
  - Tests: each case above with `SessaoFalsa` + `RelogioFalso`, asserting
    the sleeps, the number of requests, `Resposta.erro`, and the log lines
    (`caplog`). Retries count toward the limiter window.

## Phase C — Inputs and prompts

- [x] **T07 Prompt helpers** — FR-21, TR-3
  - `entrada.py`: `perguntar_opcao(texto, opcoes, entrada=input)`,
    `perguntar_texto(texto, entrada=input)`.
  - `tests/test_entrada.py`: invalid, empty, out-of-range answers re-asked;
    `5` rejected in a 1–4 menu; names: empty and `/` rejected, spaces
    trimmed.

- [x] **T08 Houses: availability, UF, filters, limit** — FR-6, FR-22, FR-23
  - `casas_legislativas.py`: `testar_casas(casas, cliente)` keeps every
    house with `ativa` and `motivo`; UF join from the spreadsheet; read old
    2-column `casas_resultado.csv`; `filtrar_sul_sudeste`; `limitar_casas`
    (1 todas, 2 primeiras 50, 3 últimas 50, 4 dez); remove
    `teste_conteudo_atualizado` (part of FR-30). Paths as parameters (TR-4).
  - `buscador.setup_busca` replaced by `entrada` + `limitar_casas`.
  - `tests/test_casas.py`: failure kept with reason; UF join; old table
    read and filtered; Sul/Sudeste on a reused table; "últimas 50" = 50.

## Phase D — Matter data

- [x] **T09 Keys, link extraction and dedup** — FR-12, FR-13
  - `materias.py`: `normalizar_link`, `chave`; `raspador.raspar_resultados`
    rewritten to use it (explicit parser, FR-11); `deduplicar_links`.
  - `tests/test_raspador.py`: links from the three real `busca_p1.html`
    (expected ids listed); `documentoacessorio`, `pesquisar-materia`,
    `/media/` excluded; `/ta`, trailing slash, absolute URL normalised.
  - `tests/test_materias.py` (dedup part): one row per key, `Palavras`
    joined in order, same id in two houses not merged.

- [x] **T10 HTML extraction** — FR-8 (parse part), FR-10 (HTML), FR-10a, FR-11
  - `materias.extrair_html(html, casa_url)` → dict of `COLUNAS_FINAIS`
    fields; `COLUNAS_FINAIS` constant; value normalisation (dates
    `dd/mm/aaaa`, whitespace, `None` → `''`).
  - Tests: exact expected values for the 6 real matter pages; **Rio Branco
    34049 `texto_original` = first block's link** (regression);
    `materia_sem_data`, `materia_sem_pdf` give empty fields;
    `Ultima Atualizacao` empty for HTML.

- [x] **T11 API extraction and lookups** — FR-10 (API), FR-10a, FR-10b
  - `materias.extrair_api(json, casa_url, consultas)`; `Consultas` cache per
    house (tipo, regime, anexadas) through `ClienteSAPL`.
  - Tests: Rio Branco 34049 / 46496 and Cascavel 43301 mapped with lookup
    fixtures (`Materia Anexada` of 46496 resolved); `texto_original` uses
    the house's scheme; ISO → `dd/mm/aaaa`; booleans → `Sim`/`Não`; failed
    lookup → empty field + warning, matter still `ok`; cache: one request
    per distinct id; output has no `ip`/`user`.

- [x] **T12 Scraping one matter with source choice** — FR-8, FR-9, FR-10
  - `materias.raspar_materia(chave, link, cliente, fontes, consultas)`:
    API first; switch house to `html` only on final 404 / non-JSON 200;
    errors after retries → `status = erro`, `erro` reason, not parsed;
    `fonte`, `raspada_em` set.
  - Tests: API house → `fonte = api`; HTML-only house switches once and
    stays (second matter requests HTML directly); 503 ×4 → `erro`, no
    switch; failed response never reaches the parser.

## Phase E — State and stages

- [x] **T13 State file** — FR-18
  - `estado.py`: `Estado(caminho)`: `registrar(etapa, chave, status, erro)`
    (append + flush), `ultimo(etapa, chave)`, `pendentes(etapa, chaves)`,
    `contagens()`.
  - `tests/test_estado.py`: append/read; last row wins; truncated last line
    ignored; reopening the file keeps the history.

- [ ] **T14 Search stage** — FR-7, FR-18
  - `buscador.buscar(casas, palavras, cliente, estado, arquivo_cru)`:
    pages until 404; failed page → `incompleta`; raw pages appended as they
    arrive; skips searches already `completa`.
  - `tests/test_buscador.py`: pagination with real fixtures (p1 → p2 →
    404); persistent 429 → `incompleta` and next keyword continues; empty
    search; resume skips `completa`.

- [ ] **T15 Matters stage** — FR-9, FR-14 (via dedup), FR-18, FR-19
  - `materias.raspar_todas(links, cliente, estado, arquivo_materias)`:
    data row flushed **before** the state row; only keys not `ok`.
  - Tests: rows appended per matter; resume skips `ok`, retries `erro` and
    unattempted; a data row without a state row is redone.

- [ ] **T16 Final table** — FR-9, NFR-2
  - `tratamento_resultado.montar_final(arquivo_materias, links)` → latest
    row per key in `COLUNAS_FINAIS` order; label stripping removed.
  - `tests/test_tratamento.py`: column order; latest attempt wins;
    `Palavras` from the links file; `Assuntos`/`texto_integral` absent.

- [ ] **T17 Downloads** — FR-14, FR-15, FR-16, FR-17
  - `download_pdf.baixar_todos(final, pasta, cliente, estado)`:
    `<host>_<id>.pdf`, streamed via `.part` + rename, `sem_pdf`, skip
    existing `ok`; fills `arquivo_pdf` / `download_status`.
  - `tests/test_download.py`: name; chunks written; failure mid-stream →
    no `.part` left, `erro`; no link → `sem_pdf`; one request per matter
    even if the key appeared twice upstream; existing file skipped.

## Phase F — Projects, main flow, summary

- [ ] **T18 Projects: create or reopen** — FR-19, FR-20, FR-24
  - `gerenciador_projetos.py`: `abrir_ou_criar(nome, raiz, entrada)` with
    the resume / other-name menu; `config.json` save/load; `os.makedirs(...,
    exist_ok=True)` for download folders; remove unused helpers (FR-30).
  - `tests/test_projetos.py`: new project; existing → menu; "outro nome"
    loops; `config.json` round-trip; existing downloads folder OK.

- [ ] **T19 `programa.py` main flow and update mode** — TR-1, FR-19, Q5
  - `main(entrada=input, cliente=None, raiz='.')`; runs only under
    `__main__`; new / resume / update modes wired to the stages; update
    mode outputs `_ATUALIZADO_<data>` files with their own state file.
  - `tests/test_programa.py`: importing `programa` runs nothing; scripted
    answers drive a new project through a fake house; update mode writes
    the `_ATUALIZADO_` files.

- [ ] **T20 Final summary** — FR-26
  - `registro.resumo(estado, caminhos)` → text with every count of FR-26 and
    the retry hint when there are failures; printed and logged at the end of
    `main`.
  - `tests/test_registro.py` (summary part): counts from a known state file;
    hint present only with failures; correct after a resume.

- [ ] **T21 End-to-end test** — TR-9, acceptance 1, 4, 5 (offline version)
  - `tests/test_ponta_a_ponta.py`: two fake houses (API / HTML-only),
    scripted 429s and one permanent failure, downloads on. Assert final
    CSV (no empty `ok` rows, no duplicate keys, `Palavras`), state, PDFs,
    summary. Resume → only the failed matter requested. Exception injected
    mid-scrape + resume → same final CSV as an uninterrupted run except
    `raspada_em`. Max 35 requests per host per 60 s (fake clock).

## Phase G — Authors script, clean-up, docs

- [ ] **T22 Authors and procedure script** — FR-27, FR-28, FR-29
  - `autoria_e_tramit.py`: `main(pasta, entrada, cliente)`; choose CSV from
    a list; output `<entrada>_autoria_tramitacao.csv`; parse by header
    names; `Tramite` as text; `status_autoria`, `status_tramitacao`, `erro`.
  - `tests/test_autoria.py`: real autoria/tramitação fixtures parsed;
    chosen file read and input untouched; failure recorded.

- [ ] **T23 Clean-up** — FR-30
  - Remove `testes.py` and any remaining dead code; no direct
    `requests.get` left (`grep` check as a test:
    `tests/test_sem_requests_direto.py`).

- [ ] **T24 Docs** — NFR-5
  - README: new columns, `fonte`/`status`, resume, log, summary, how to run
    tests, CI badge, remove the "known problem" warning. ROADMAP: tick the
    items done. Constitution/tech-stack untouched unless something changed.

## Phase H — Validation

- [ ] **T25 Update `validation.md`** — it was written before implementation;
  align commands, prompt answers, file names, column names and the log
  regex (§2.2) with what was built.
- [ ] **T26 Run validation**, record results in `validation.md`, fix what
  fails (new tasks if needed), then merge the branch into `main`.

## Traceability (TR-10)

| Requirement | Tasks | Tests |
|---|---|---|
| FR-1 | T05, T23 | `test_http_sapl`, `test_sem_requests_direto` |
| FR-2 | T05 | `test_http_sapl`, `test_ponta_a_ponta` |
| FR-3 | T06 | `test_http_sapl` |
| FR-4 | T06 | `test_http_sapl` |
| FR-5 | T06 | `test_http_sapl` |
| FR-6 | T08 | `test_casas` |
| FR-7 | T14 | `test_buscador` |
| FR-8 | T10, T12 | `test_materias` |
| FR-9 | T12, T15, T16 | `test_materias`, `test_tratamento`, `test_ponta_a_ponta` |
| FR-10 | T10, T11, T12 | `test_materias` |
| FR-10a | T10, T11 | `test_materias`, `test_tratamento` |
| FR-10b | T03, T11 | `test_fixtures`, `test_materias` |
| FR-11 | T09, T10 | `test_raspador`, `test_materias` |
| FR-12 | T09 | `test_raspador`, `test_materias` |
| FR-13 | T09 | `test_materias`, `test_ponta_a_ponta` |
| FR-14 | T09, T17 | `test_download` |
| FR-15 | T17 | `test_download` |
| FR-16 | T17 | `test_download` |
| FR-17 | T17 | `test_download` |
| FR-18 | T13, T14, T15 | `test_estado`, `test_buscador`, `test_materias` |
| FR-19 | T15, T18, T19 | `test_projetos`, `test_programa`, `test_ponta_a_ponta` |
| FR-20 | T18 | `test_projetos` |
| FR-21 | T07 | `test_entrada` |
| FR-22 | T08 | `test_casas` |
| FR-23 | T08 | `test_casas` |
| FR-24 | T18 | `test_projetos` |
| FR-25 | T04 | `test_registro` |
| FR-25a | T06 | `test_http_sapl` |
| FR-26 | T20 | `test_registro`, `test_ponta_a_ponta` |
| FR-27 | T22 | `test_autoria` |
| FR-28 | T22 | `test_autoria` |
| FR-29 | T22 | `test_autoria` |
| FR-30 | T08, T18, T23 | `test_sem_requests_direto` (dead code: review, no test) |
| TR-1 | T19 | `test_programa` |
| TR-2 | T05 | `test_http_sapl` |
| TR-3 | T07 | `test_entrada` |
| TR-4 | T08, T18 | `test_casas`, `test_projetos` |
| TR-5–TR-8 | T01, T03 | `test_conftest`, `test_fixtures` |
| TR-9 | T21 | `test_ponta_a_ponta` |
| TR-11 | T02 | CI run |
| NFR-2 | T16 | `test_tratamento` |
| NFR-5 | T24 | review |
