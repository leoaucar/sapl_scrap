# Plan: Runtime improvements

- **Spec:** [spec.md](spec.md) · **Status:** Approved · **Date:** 2026-10-24
- **Branch for implementation:** `spec/2026-10-24-runtime-improvements`
  (created after this plan is committed; merged after `validation.md` passes)

## 1. Approach in one paragraph

Put every SAPL request behind one small HTTP client that enforces the
per-host rate limit, retries correctly and logs each request. On top of it,
rewrite each stage (search → links → matters → final table → downloads) as a
plain function with explicit inputs and outputs that records its progress in
a per-project state file as it goes. Matter data comes from the SAPL JSON API
when available, with the HTML page as fallback. `programa.py` becomes a thin
`main()` that asks the questions and calls the stages. Everything is tested
offline with fake HTTP and a fake clock. The layout stays flat (no package);
restructuring into a package is the next spec ("code organization").

## 2. Findings from real pages (2026-10-24)

Collected from Rio Branco/AC, ALEAC and Cascavel/PR (≈ 45 requests in total,
no 429s). Saved in `tests/fixtures/sapl/<host>/`, indexed with URL, status and
date in `tests/fixtures/sapl/index.json`. API fixtures had `ip`/`user`
removed.

| Topic | Finding | Consequence |
|---|---|---|
| Matter page fields | Same 25 `div_id_*` blocks in all 3 houses. No `div_id_data`, `div_id_assuntos`, `div_id_texto_integral`. Date in `div_id_data_apresentacao`. | FR-10a mapping (§5). |
| Duplicate block | Rio Branco renders `div_id_texto_original` **twice**; only the first has the `<a>`. Current code takes the last → empty PDF link. | Take the first block that has a link. Regression test with that fixture. |
| Field values | Value is in `.form-control-static` inside each block; label in `p.control-label`. | Read the value element instead of stripping labels with `str.replace` (removes the label-stripping in `tratamento_resultado.py`). |
| JSON API | `/api/materia/materialegislativa/<id>` → 200 JSON on both houses tried. ISO dates, booleans, absolute PDF URL (`http://`), `data_ultima_atualizacao`. `tipo`, `regime_tramitacao`, `anexadas`, `autores` are ids. | Primary source; ids resolved by cached lookups (§5.3). |
| Lookups | `/api/materia/tipomaterialegislativa/<id>`, `/api/materia/regimetramitacao/<id>` return `descricao`/`__str__`. | One request per distinct id per house, cached in memory for the run. |
| Search links | Matter links are relative `/materia/<id>`. The page also links `/materia/documentoacessorio/<id>`, `/materia/pesquisar-materia` and `/media/...pdf`. | Key by regex `^/materia/(\d+)/?$` after `urljoin` (§5.4). |
| Pagination | `page=999` → 404 on all three. Empty search → 200 with "Foram encontrados 0 registros". | Confirms FR-7. |
| PDFs (Q4) | Same host, under `/media/sapl/public/materialegislativa/<ano>/<id>/`. | Downloads share the host's limit. |
| Autoria / tramitação pages | Tables with headers `Autor, Descrição, Primeiro Autor` and `Data Tramitação, Unidade Local, Unidade Destino, Status`; latest procedure first. | Keep HTML parsing in `autoria_e_tramit.py`, read by header name. |

## 3. Files

Flat layout kept on purpose (package restructuring = next spec).

| File | Change |
|---|---|
| `http_sapl.py` | **New.** `ClienteSAPL`: shared session, per-host limiter, retry, request log. |
| `estado.py` | **New.** State file (append / read / latest status per key). |
| `entrada.py` | **New.** Prompt helpers with injectable input function. |
| `registro.py` | **New.** Logging setup (terminal + project log) and final summary. |
| `materias.py` | **New.** Matter keys, link normalisation, dedup, API and HTML extraction, final column list. |
| `buscador.py` | Rewritten on top of `ClienteSAPL` + state; menu moves to `entrada.py`. |
| `raspador.py` | Keeps link extraction from search HTML; matter scraping moves to `materias.py`. |
| `casas_legislativas.py` | Availability test through the client, keeps failures with reason, UF column; dead code removed. |
| `download_pdf.py` | Streamed, stable names, `.part` file, status. |
| `tratamento_resultado.py` | Builds the final table from extracted fields (no label stripping); column order in one place. |
| `gerenciador_projetos.py` | Create **or** reopen a project; unused helpers removed. |
| `programa.py` | `main()` only: questions + calling stages; runs under `if __name__ == '__main__'`. |
| `autoria_e_tramitacao/autoria_e_tramit.py` | Uses the client; chooses the CSV at the prompt; writes a new file; `Tramite` as text. |
| `testes.py` | **Removed** (replaced by `tests/`). |
| `tests/…`, `pyproject.toml`, `.github/workflows/tests.yml` | **New.** §8, §9. |
| `README.md`, `ROADMAP.md` | Updated (NFR-5). |

## 4. HTTP client (`http_sapl.py`) — FR-1 to FR-5, FR-25a, TR-2

```text
ClienteSAPL(sessao=None, relogio=time.monotonic, dormir=time.sleep,
            limite_por_minuto=35, max_tentativas=4, logger=...)
  .get(url, *, stream=False, timeout=(10, 30)) -> Resposta
Resposta: ok: bool, status: int|None, texto/json/conteudo, erro: str ('' if ok),
          tentativas: int
```

- **Limiter.** Per host (`urlparse(url).hostname`), a sliding window: a
  `deque` with the times of the last 35 requests. Before a request, if the
  deque is full and its oldest entry is < 60 s old, sleep until it is 60 s
  old. Every attempt (including retries) counts. One constant
  `LIMITE_POR_MINUTO = 35` at the top of the module.
- **429.** Read `Retry-After` (seconds; default 60; capped at 300). Block the
  **whole host** until then (all requests to that host wait), then retry.
- **Network error / timeout / 5xx.** Retry with waits of 5 s, 15 s, 45 s.
- **Attempts.** At most `max_tentativas` (4) per request, for any mix of
  causes. After that: `ok=False`, `erro` = `"HTTP 429"`, `"HTTP 503"`,
  `"timeout"`, `"conexao"`.
- **No retry** for 404 and other 4xx: returned at once with `ok=False`,
  `status` set. Callers decide (404 = end of pagination / no API).
- **Log.** One `DEBUG` line per attempt in the project log:
  `host | url | status-or-error | tentativa n | espera s`. This is what
  acceptance criterion 2 is checked against.
- **Why not `urllib3.Retry`:** it would handle 429/5xx, but not the per-host
  window, the host-wide block after a 429, the injected clock, or per-attempt
  logging. A ~80-line loop is simpler to test than combining both.
- Single instance per run, created in `main()` and passed to every stage.

## 5. Matter data (`materias.py`) — FR-8 to FR-14

### 5.1 Key and normalisation (FR-12)

- `chave = (host, sapl_id)`, written as `"<host>/<sapl_id>"` in files.
- `normalizar_link(casa_url, href)`: `urljoin`, drop query/fragment, drop
  `/ta` and trailing `/`, force the house's scheme; returns
  `(link_canonico, sapl_id)` or `None` if it does not match
  `^/materia/(\d+)$`.

### 5.2 Dedup (FR-13)

- After link extraction: group by `chave`; `Palavras` = keywords joined by
  `"; "` in order of first appearance; `Link Casa` from the first row.
- Applied before scraping and therefore before downloads (FR-14).

### 5.3 Sources (FR-10, FR-10a, FR-10b)

- **API probe per house:** the first matter of a house is requested from the
  API. Final 404, or a 200 whose body is not JSON → the house is marked
  `html` for the rest of the run (logged once). Errors after retries
  (timeouts, 5xx, 429) do **not** switch source; the matter is `erro`.
- **Lookups:** `tipo` and `regime_tramitacao` names, and the `__str__` of
  each `anexadas` id (`/api/materia/materialegislativa/<id>`), cached per
  house for the run. A failed lookup leaves that field empty and logs a
  warning; the matter stays `ok`.
- **HTML fallback:** for each field, find the first `div#div_id_<campo>`
  whose `.form-control-static` (or `<a>` for the PDF) is non-empty.
  Explicit `html.parser` everywhere (FR-11).
- **Field mapping:**

  | Column | API | HTML (`div_id_…`) |
  |---|---|---|
  | `Titulo` | `__str__` | `h1.page-header` |
  | `Ementa` | `ementa` | `ementa` |
  | `Ano` / `Numero` | `ano` / `numero` | `ano` / `numero` |
  | `Data` | `data_apresentacao` | `data_apresentacao` |
  | `Observacao` | `observacao` | `observacao` |
  | `Tipo de Materia Legislativa` | lookup `tipo` | `tipo` |
  | `texto_original` | `texto_original` (host's scheme) | first `texto_original` with `<a>`, joined to house URL |
  | `Indexacao` | `indexacao` | `indexacao` |
  | `Em Tramitacao` | `em_tramitacao` → `Sim`/`Não` | `em_tramitacao` |
  | `Regime Tramitacao` | lookup `regime_tramitacao` | `regime_tramitacao` |
  | `Materia Anexada` | `__str__` of `anexadas`, `"; "`-joined | `materia_principal_set__materia_anexada` |
  | `Resultado` | `resultado` | `resultado` (if present) |
  | `Data Publicacao` | `data_publicacao` | `data_publicacao` |
  | `Numero Protocolo` | `numero_protocolo` | `numero_protocolo` |
  | `Ultima Atualizacao` | `data_ultima_atualizacao` | — (empty) |

- **Normalisation of values (both sources):** dates as `dd/mm/aaaa`
  (what the researcher sees on the site; HTML already uses it, ISO from the
  API is converted; `Ultima Atualizacao` as `dd/mm/aaaa hh:mm`); whitespace
  and line breaks collapsed to single spaces; `None` → `''`.
- `ip`, `user` and any field not listed above are ignored (FR-10b).

### 5.4 Final columns (NFR-2)

Single list `COLUNAS_FINAIS` in `materias.py`, used by every writer:

```
Link Materia, Link Casa, Palavras, Titulo, Ementa, Ano, Data, Numero,
Observacao, Tipo de Materia Legislativa, texto_original,
Indexacao, Em Tramitacao, Regime Tramitacao, Materia Anexada, Resultado,
Data Publicacao, Numero Protocolo, Ultima Atualizacao,
sapl_id, fonte, status, erro, raspada_em, arquivo_pdf, download_status
```

Existing columns keep their relative order; `Assuntos` and `texto_integral`
are gone; the rest is appended.

## 6. Project files, state and resume (`estado.py`) — FR-18 to FR-20

### 6.1 Files in `<nome>_proj/`

| File | Written | Content |
|---|---|---|
| `casas_resultado.csv` | stage 1 | `url, ativa, motivo, uf` (old 2-column files still read) |
| `<nome>_resultados_crus_casas.csv` | per search page, appended | as today (removed in the parallelism spec) |
| `<nome>_links_totais.csv` | end of search | deduplicated links: `chave, Link Materia, Link Casa, Palavras` |
| `<nome>_materias_legislativas.csv` | per matter, appended | one row per attempt, all `COLUNAS_FINAIS` |
| `<nome>_estado.csv` | per event, appended | progress (below) |
| `<nome>_resultado_final.csv` | end of run (rebuilt) | latest row per `chave`, `COLUNAS_FINAIS` |
| `<nome>.log` | always | `INFO` + `DEBUG` (per request) |
| `downloads/` | per PDF | `<host>_<sapl_id>.pdf` |

### 6.2 State file

Append-only CSV, flushed after every row: `etapa, chave, status, erro, quando`.

- `etapa = busca`, `chave = "<host>|<palavra>"`, `status = completa|incompleta`
- `etapa = materia`, `chave = "<host>/<id>"`, `status = ok|erro`
- `etapa = pdf`, `chave = "<host>/<id>"`, `status = ok|erro|sem_pdf`
- `etapa = execucao`, `chave = links_prontos`, `status = ok` (search stage
  finished and links file written)

Reading: the **last** row per `(etapa, chave)` wins. A row cut by a crash
(last line incomplete) is ignored.

### 6.3 Resume rules

1. If `links_prontos` is not recorded: redo only searches not marked
   `completa` (raw pages of incomplete searches are appended again; dedup
   absorbs repeats). Then rebuild the links file and record `links_prontos`.
2. Scrape every `chave` in the links file whose latest `materia` status is
   not `ok`.
3. Rebuild `_resultado_final.csv` from `_materias_legislativas.csv`.
4. Download each matter whose latest `pdf` status is not `ok`/`sem_pdf`, or
   whose file is missing.

### 6.4 Prompts around projects (FR-19, FR-20)

- Name typed → folder exists → menu: `1- retomar este projeto`,
  `2- escolher outro nome`. Never `os.mkdir` on an existing folder.
- Resuming skips the house/limit questions (answers stored in
  `<nome>_proj/config.json` when the project was created: keywords, filter,
  limit, download choice).

### 6.5 Update mode (Q5)

Same machinery: links come from the given `_resultado_final.csv` (deduped by
`chave`, keeping its `Palavras`), output to
`_resultado_final_ATUALIZADO_<dd_mm_aaaa>.csv` with its own state file
`<nome>_estado_ATUALIZADO_<dd_mm_aaaa>.csv`, downloads in
`downloads<dd_mm_aaaa>/` (created with `exist_ok=True`). The update-mode
filter by `Relevante` (commented out today) stays out of scope.

## 7. Other stages

- **Availability test (FR-6):** through the client with a short timeout
  `(5, 5)` and `max_tentativas=2`; every house kept with `ativa` and
  `motivo`. UF joined from `casas_legislativas.xlsx` by `URL do serviço`.
- **Sul/Sudeste with reused table (FR-22):** filter on the `uf` column; old
  tables without `uf` get it from the spreadsheet join.
- **Limit menu (FR-21, FR-23):** options 1–4 only; "50 últimas" =
  `casas[-50:]`.
- **Search (FR-7):** per house + keyword, pages until 404; a failed page
  (`ok=False` and status ≠ 404) → state `incompleta`, logged, go to next
  keyword. Raw pages appended as they arrive.
- **Downloads (FR-15–FR-17):** `get(..., stream=True, timeout=(10, 60))`;
  write to `downloads/<host>_<id>.pdf.part` in 64 KB chunks, rename on
  success; delete `.part` on any failure. No link → `sem_pdf`.
  `arquivo_pdf` and `download_status` written back into the final CSV after
  the download stage.
- **Prompts (FR-21, TR-3):** `entrada.perguntar_opcao(texto, opcoes,
  entrada=input)` loops until the answer is one of `opcoes`;
  `perguntar_texto(...)` for names (non-empty, no `/`).
- **Logging and summary (FR-25, FR-26):** `registro.configurar(pasta, nome)`
  sets a terminal handler (`INFO`) and a file handler (`DEBUG`).
  `registro.resumo(estado, caminhos)` counts from the state file, so the
  summary is also correct after a resume.
- **Authors and procedure (FR-27–FR-29):** lists the `.csv` files in its
  folder and asks which one; output `<entrada>_autoria_tramitacao.csv`;
  parses tables by header names; `Tramite` =
  `"<data> | <unidade local> | <unidade destino> | <status>"` of the latest
  row; columns `status_autoria`, `status_tramitacao`, `erro`. Stays HTML-based
  (the API alternative is noted for the code-organization spec).

## 8. Testing (spec §6)

### 8.1 Infrastructure

- `pyproject.toml` with only `[tool.pytest.ini_options]` (`testpaths =
  ["tests"]`, `addopts = "--cov=. --cov-report=term-missing"`) and
  `[tool.coverage.run] omit = ["tests/*"]`. The code-organization spec will
  extend it.
- `tests/conftest.py`:
  - `bloquear_rede` (autouse): monkeypatches `socket.socket.connect` to
    raise, so any real connection fails the test (TR-6).
  - `RelogioFalso`: `agora()` and `dormir(s)` that only advance time and
    record the sleeps.
  - `SessaoFalsa`: maps `(method, url)` → a list of scripted responses
    (status, headers, body or fixture file, or an exception to raise);
    records every request. Implements the `requests.Session` subset the
    client uses (`get` with `stream`, `iter_content`, `headers`).
  - `fixture(caminho)`: loads `tests/fixtures/...` files.
  - `projeto_tmp`: an empty project folder in `tmp_path` plus a minimal
    `casas_legislativas.xlsx` / keywords file.
- Synthetic fixtures (made from real ones, documented in
  `tests/fixtures/README.md`): matter page without date, without PDF, and
  without API (HTML-only house); a 429 response is built in code.

### 8.2 Test modules and what they cover

| Module | Covers |
|---|---|
| `test_http_sapl.py` | limiter window and per-host independence; 429 with/without `Retry-After`, cap, host-wide block; 5xx/timeout/connection backoff; give-up reasons; 404 not retried; one log line per attempt |
| `test_casas.py` | availability with failures kept; UF join; old 2-column table; Sul/Sudeste on reused table; limit menu slices |
| `test_buscador.py` | pagination to 404; persistent 429/500 → `incompleta`; empty search; raw pages appended |
| `test_raspador.py` | link extraction from the three real search pages; exclusions; relative/absolute links |
| `test_materias.py` | key normalisation; dedup and `Palavras`; API mapping (2 real JSON fixtures + lookups); HTML mapping (6 real pages); **Rio Branco duplicate `texto_original`**; API → HTML switch only on 404/non-JSON; failed request → `erro`, not parsed; no `ip`/`user` in output |
| `test_estado.py` | append/read; last row wins; truncated last line ignored |
| `test_download.py` | stable name; streamed write; `.part` removed on failure; `sem_pdf`; once per matter; skip existing |
| `test_entrada.py` | invalid/empty/out-of-range answers re-asked; `5` rejected; name validation |
| `test_projetos.py` | new vs existing project; resume/other-name menu; `config.json` round-trip; existing downloads folder |
| `test_tratamento.py` | `COLUNAS_FINAIS` order; final table = latest row per key; update-mode output names |
| `test_registro.py` | log handlers; summary counts from a known state file |
| `test_autoria.py` | CSV chosen at prompt; new output file; `Tramite` text from real fixtures; failures recorded |
| `test_ponta_a_ponta.py` | TR-9: two fake houses (one API, one HTML-only), scripted 429s and one permanent failure; checks final CSV, state, PDFs, summary; then resume → only the failed matter requested again; interrupted run (exception mid-scrape) + resume equals uninterrupted run except timestamps |

### 8.3 CI (TR-11)

`.github/workflows/tests.yml`: on `push` and `pull_request`; matrix Python
`3.10`, `3.12`; `actions/checkout`, `actions/setup-python`,
`pip install -r requirements-dev.txt`, `pytest`. README badge.

## 9. Implementation order

Each step ends with its tests passing; `tasks.md` will break them down.

1. Test infrastructure (`pyproject.toml`, `conftest.py`, fixtures README) +
   CI workflow — so every later step is checked from the start.
2. `http_sapl.py` + `registro.py` (logging part).
3. `entrada.py`; prompt fixes (FR-21–FR-23).
4. `materias.py`: keys, dedup, HTML extraction, then API extraction.
5. `estado.py`.
6. Rewrite stages: casas → busca → links → matérias → tratamento → downloads.
7. `gerenciador_projetos.py` (create/reopen, `config.json`) + `programa.py`
   `main()` + update mode.
8. Summary (`registro.resumo`) + end-to-end test.
9. `autoria_e_tramit.py`.
10. Clean-up (FR-30), README, ROADMAP.
11. `validation.md` run against real sites (manual).

## 10. Expected cost of a run (with the limit)

- Per matter: 1 request (API or HTML) + 1 per PDF if downloading.
- Per house: lookups (≈ 5–20 requests: distinct types, regimes, attached
  matters) + search pages + 1 API probe.
- The 2026-10-15 test (≈ 1 200 unique matters, 2 large houses) ≈ 40–60 min
  sequentially without PDFs; roughly double with PDFs. Parallelism (spec 3)
  brings it back down.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Other SAPL versions use different `div_id`s or no API | HTML fallback + `fonte` column; validation run includes ≥ 1 house outside AC/PR; missing fields are empty, not errors |
| The limit is not exactly 35/min, or differs per house | Single constant; 429 handling still works if it is lower |
| Search endpoint is limited after all | Already rate-limited (Q3) |
| State and data files diverge after a crash | State written **after** the data row is flushed; on resume a data row without state is treated as not done and redone |
| Long runs and large logs | `DEBUG` only to file; log rotation left to later specs |
| Overlap with the code-organization spec | Keep new modules flat and small; no renames of existing public functions beyond what the stages need |

## 12. Decisions taken in this plan (for review)

- Custom retry/limiter loop instead of `urllib3.Retry` (§4).
- Dates normalised to `dd/mm/aaaa` for both sources (§5.3).
- Project answers stored in `config.json` so resume asks nothing (§6.4).
- `autoria_e_tramit.py` stays HTML-based in this spec (§7).
- `pyproject.toml` only for pytest/coverage config now (§8.1).
