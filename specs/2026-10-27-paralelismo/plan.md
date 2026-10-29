# Plan: Parallel runs (several houses at once)

- **Spec:** [spec.md](spec.md) · **Status:** Approved 2026-10-29 · **Date:** 2026-10-27
- **Branch for implementation:** `spec/2026-10-27-paralelismo`, from `main`
  (spec 2 merged on 2026-10-27)

## 1. Approach in one paragraph

First make every shared piece safe for threads without changing behaviour:
the HTTP client, the append-only files, the cache, the test helpers. Then add
the server ceiling to the client, with its history and the adaptive slow-down,
tested single-threaded with the fake clock. Then add one small module that runs
a function per house on a thread pool and handles Ctrl+C and progress. Finally,
move each flow (new/resume, update, authors/procedure, availability test) onto
it, house by house, proving at every step that 1 worker and 8 workers give the
same files. The real-site ramp in validation sets the final defaults.

## 2. Findings used by this plan (2026-10-27)

| Topic | Finding | Consequence |
|---|---|---|
| Shared servers | 10/10 Acre houses and 37/60 sampled houses resolve to `201.54.51.178`; 3/60 to `.179`; 20/60 do not resolve | Server ceiling per IP (spec FR-6); validation groups requests by IP |
| `requests.Session` | Not documented as thread-safe | One session per worker thread (`threading.local`) |
| `time.sleep` in waits | Ctrl+C reaches only the main thread; a worker sleeping 60 s would hold the exit | Waits use `threading.Event.wait`, so a stop wakes them at once |
| Fake clock with threads | `RelogioFalso.dormir` moves one shared time; recorded "send" times taken outside the client's lock can be out of order | Limit tests read the client's own reservation times (a hook called under its lock) |
| Downloads | `baixar_todos` works on the final table after all matters | Per-house download step; the final table's download columns are filled from the state file at the end (same values as today) |
| Links file | Written once, after all searches | Rebuilt at the end of the run from the pages files, in house order (no requests); a resumed run without it rebuilds it the same way |

## 3. Layout changes

```
sapyl/
  padroes.py        NEW, layer 1: LIMITE_POR_SITE (35), JANELA_SEGUNDOS, MARGEM_SEGUNDOS,
                    LIMITE_POR_SERVIDOR (120), PISO_POR_SERVIDOR (35),
                    CASAS_AO_MESMO_TEMPO (8), JANELA_LENTIDAO (600 s),
                    validar_paralelo(dict) -> dict
  cliente_http.py   locks, per-thread sessions, server windows, slow-down, interruptible waits
  estado.py         ArquivoCSV, Estado and Cache get a lock each
  registro.py       house prefix on log lines (thread-local), summary additions
  execucao.py       NEW, layer 6: por_casa(...) pool, Ctrl+C, progress line
  busca.py          buscar_casa(...) for one house (buscar() keeps working for tests)
  downloads.py      baixar_da_casa(...), preencher_downloads(final, estado, pasta)
  autoria.py        processar(...) groups pending keys by house and uses the pool
  interface/principal.py  flows call execucao.por_casa
```

Layer table in `tests/test_camadas.py`: `padroes` joins layer 1, `execucao`
joins layer 6 (with `projeto`). `cliente_http` imports its constants from
`padroes` (one place, FR-15); the old names stay as aliases in
`cliente_http` so existing imports keep working.

## 4. The client (`cliente_http.py`)

- **Lock.** One `threading.Lock` guards every window, block and history write.
  `_aguardar_vez(host)` loops: under the lock, prune the host and server
  windows; if both have room and the host is not blocked, append the send time
  to both, call the optional `ao_reservar(host, servidor, t)` hook, save the
  history and return; otherwise compute the wait (the longer of the two) and
  leave the lock. The wait happens outside the lock.
- **Servers.** New argument `servidor_de: Callable[[str], str | None] | None`.
  `None` (the default, used by every existing test) means each host is its own
  server, so there's no extra limit. Production passes `resolver_servidor`,
  which calls `socket.gethostbyname` once per host (cached, under the lock) and
  returns `None` when the name does not resolve. Hosts with no server only
  have the site limit.
- **Ceilings.** `limite_por_servidor` (int) is the starting ceiling; a dict
  `_teto[servidor]` holds the current one per server.
- **Slow-down (FR-8).** On a 429, record `(t, host, servidor)`. If the
  records for that server in the last `JANELA_LENTIDAO` seconds cover ≥ 2
  hosts and no reduction happened in that span, set
  `_teto[servidor] = max(PISO_POR_SERVIDOR, _teto[servidor] // 2)`, log a
  warning and append `(servidor, old, new)` to `reducoes`. Clear that server's
  records after a reduction so the same burst is not counted twice.
- **History (FR-7).** The JSON gains `"servidores": {ip: [epoch, ...]}`, saved
  and loaded like `"requisicoes"`. Older files without it still load.
- **Sessions.** When no `sessao` is injected, `self._local = threading.local()`
  and each thread creates its own `requests.Session` on first use. An injected
  session (tests) is shared, as today.
- **Interruptible waits.** New argument `parar: threading.Event | None`. The
  default `dormir` becomes `lambda s: parar.wait(s)` when an event is given,
  and `get()` raises `Interrompido` (a new exception, subclass of
  `KeyboardInterrupt`) when the event is set, before sending and after any
  wait. Tests keep injecting the fake `dormir`.
- **Test scaling.** `janela_segundos` and `margem_segundos` become constructor
  arguments (defaults from `padroes`), so thread tests can use a 0.2 s window.
- The DEBUG line format is unchanged (the validation script maps hosts to IPs
  with its own DNS lookup).

## 5. Shared files (`estado.py`)

- `ArquivoCSV.anexar` writes the whole line and flushes under a per-instance
  lock. Each file is opened once per run and the instance is shared by all
  workers.
- `Estado.registrar` takes its own lock around the append and the in-memory
  update; reads (`status`, `contagens`) read the dict (safe under the GIL for
  single lookups; `contagens` copies under the lock).
- `Cache` methods take a lock around read-modify-save.

## 6. The pool (`execucao.py`)

```python
def por_casa(casas, tarefa, n, parar, progresso=None, a_cada=60.0) -> dict[str, BaseException | None]
```

- Runs `tarefa(casa)` for each house on a `ThreadPoolExecutor(n)`, keeping
  the input order for results. While a worker runs, `registro.casa_atual(host)`
  sets a thread-local value that the log formatter turns into a `[host] `
  prefix (FR-13).
- The main thread waits with `concurrent.futures.wait(..., timeout=1)` in a
  loop, so Ctrl+C reaches it. On `KeyboardInterrupt`: set `parar`, cancel
  futures not started, wait for running ones (they stop at their next request
  or wait, or when their request in flight ends), then re-raise. The existing
  handler in `main` prints the resume message.
- An exception in one house's task (a bug, a disk error) is logged with its
  traceback in the log file; the other houses continue; the run then fails
  with a clear message after all houses end (no silent loss, constitution §1).
- Every `a_cada` seconds the main thread calls `progresso()` and logs its line
  (houses done / running / waiting, matters ok / errors so far, from the state).
- With `n == 1` the same code runs one house at a time (FR-2), which is what
  the equivalence tests compare against.

## 7. Flows

### 7.1 New or resumed project (`principal.executar_projeto`)

1. Prepare houses. If the table is not reused, the availability test runs
   through `por_casa` (FR-3), one request per house; results are collected in
   table order.
2. Read once the links already found (old raw file + pages file), grouped by
   house.
3. `por_casa(active houses, pipeline)`, where `pipeline(casa)`:
   - searches the keywords still pending for that house (`busca.buscar_casa`),
     appending pages to the shared pages file and getting back the links found
     in this run;
   - deduplicates that house's links (old + new), FR-11;
   - scrapes its pending matters (`materias.raspar_todas` with the shared
     `Fontes`, cache and matters file);
   - if downloads were asked, downloads its `ok` matters
     (`downloads.baixar_da_casa`), recording each in the state.
4. After the pool: rebuild the links file from the pages in house order,
   `montar_final` with those links (same order as sequential, FR-9), then
   `downloads.preencher_downloads(final, estado, pasta)` to fill
   `arquivo_pdf` / `download_status` from the state.
5. Summary (FR-14): elapsed time, `n`, per-server ceiling and reductions.

### 7.2 Update mode

Links from the input table are grouped by house; `por_casa` runs matters (+
downloads) per house; then the same assembly as 7.1 step 4, plus the extra
columns from spec 2.

### 7.3 Authors and procedure

`autoria.processar` groups the pending keys by house and runs
`raspar_autoria` per house through `por_casa`; the partial file and the state
are shared instances. The join at the end is unchanged.

### 7.4 Settings (FR-15, FR-16)

- New projects: `config['paralelo'] = {'casas_ao_mesmo_tempo': 8,
  'limite_por_servidor': 120}` from `padroes`.
- Every run (new, resume, update, option 3): `padroes.validar_paralelo(
  config.get('paralelo', {}))` fills missing keys with defaults and raises
  `ValueError` with the key and the allowed range for bad values; `main`
  prints it and exits with code 2 before any request. Option 3 on a plain CSV
  uses the defaults.
- `main` builds the client with `servidor_de=resolver_servidor`,
  `limite_por_servidor=...` and `parar=` the run's event.

## 8. Testing (spec §6)

| Module | Covers |
|---|---|
| `test_padroes.py` | defaults, `validar_paralelo` (missing, wrong type, below floor) — TR-7 |
| `test_cliente_http.py` | server window with fake clock; stricter of the two wins; history with `servidores`; slow-down rules and floor; `Interrompido` on stop — TR-1, TR-3 |
| `test_concorrencia.py` | real threads, 0.2 s window: no host > limit and no server > ceiling in the `ao_reservar` times; shared `ArquivoCSV`/`Estado`/`Cache` under 16 threads — TR-2, TR-6 |
| `test_execucao.py` | order of results, one house failing does not stop others, Ctrl+C sets `parar` and re-raises, progress callback — TR-5 (unit) |
| `test_principal.py` / `test_ponta_a_ponta.py` | 1 vs 8 workers give identical finals (except `raspada_em`), same state, same downloads; interruption + resume; update and option 3 with workers; settings saved and validated — TR-4, TR-5, TR-7, TR-8 |
| `test_compat_fase1.py` | Phase 1 project still resumes and updates with workers |

Helpers: `SessaoFalsa` gets a lock around its queues and request list;
`RelogioFalso` gets a lock; `SaplFalso` is read-only after setup (already safe).

## 9. Implementation order

1. `padroes.py` and settings in `config.json`.
2. Thread-safe files and test helpers (no behaviour change).
3. Client: lock, per-thread sessions, interruptible waits, window arguments.
4. Client: server windows + history; then the slow-down.
5. `execucao.por_casa`, log prefix, progress line.
6. Availability test in parallel.
7. New/resume pipeline per house, downloads per house, final assembly.
8. Update mode and option 3 on the pool.
9. Summary additions; concurrency and end-to-end tests.
10. Docs; `validation.md`; validation ramp on real sites; merge.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Race conditions show up only on real runs | Locks are few and coarse; thread tests with many workers; every flow compared 1 vs 8 workers |
| The shared server blocks our address anyway | Low starting ceiling (120/min), slow-down on 429s from 2 houses, ramp in validation before raising defaults |
| DNS lookups add delay or fail | One lookup per host per run, in the worker that first needs it; failure means "no server", the house then fails with `dns` as today |
| Interleaved terminal output is hard to read | `[host]` prefix on every line and the periodic overall line |
| A house's bug kills the run silently | Per-house exceptions are logged with traceback and reported at the end |
| Ctrl+C waits for a slow request | Request timeout is already ≤ 30 s; waits are interruptible |

## 11. Decisions taken in this plan (for review)

- New module `padroes.py` holds every limit and default (FR-15), and
  `cliente_http` re-exports its old names.
- A server is an IP address, one ceiling per IP (spec Q2 left open for the
  ramp).
- `Interrompido` subclasses `KeyboardInterrupt`, so the existing Ctrl+C
  handling in `main` covers it.
- The links file is rebuilt at the end from the pages files instead of being
  written by workers.
- The log line format for requests stays as it is.
