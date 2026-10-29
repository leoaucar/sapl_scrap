# Tasks: Parallel runs (several houses at once)

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Status:** Approved 2026-10-29
- **Branch:** `spec/2026-10-27-paralelismo` (from `main`)

Rules for every task (same as spec 2):
- A task is done when its tests are written, `pytest` passes offline, `ruff`
  passes and CI is green on the branch.
- One commit per task, at most. Message in Portuguese, starting with the task
  id. No AI co-author trailers. Check pytest's own exit code before
  committing.
- Tick the box here in the same commit.

## Phase A: Foundations (no behaviour change)

- [ ] **T01 Defaults and settings** (FR-15, FR-16, TR-7)
  - `sapyl/padroes.py` with every limit and default; `cliente_http` imports
    from it and keeps its old names as aliases. Add `padroes` to layer 1 in
    `test_camadas.py`.
  - `validar_paralelo()`; new projects save `paralelo` in `config.json`;
    `main` validates it on every run and exits with code 2 on a bad value.
  - Tests: `test_padroes.py`; new project saves the defaults; an old project
    without `paralelo` runs with them; a bad value stops before any request.
- [ ] **T02 Thread-safe files and test helpers** (FR-10, TR-6)
  - Locks in `ArquivoCSV`, `Estado`, `Cache`; `SessaoFalsa` and
    `RelogioFalso` get locks.
  - `test_concorrencia.py` (first part): 16 threads appending to one
    `ArquivoCSV`, registering in one `Estado` and saving to one `Cache`; every
    row read back intact, none lost.
- [ ] **T03 Client ready for threads** (plan §4)
  - Lock around windows, blocks and history; per-thread sessions when none is
    injected; `parar` event, interruptible waits and `Interrompido`;
    `janela_segundos` / `margem_segundos` arguments; `ao_reservar` hook.
  - Tests: existing client tests unchanged; stop during a wait raises
    `Interrompido` at once; per-thread sessions are distinct.

## Phase B: Server ceiling

- [ ] **T04 Server windows and history** (FR-6, FR-7, TR-1)
  - `servidor_de` argument, `resolver_servidor()`, per-server window with the
    stricter-of-two rule, `servidores` in the history file.
  - Tests (fake clock): 3 hosts on one server with ceiling 70: the 71st
    request in a window waits; hosts without a server have only the site
    limit; history round trip; an old history file without `servidores`
    loads; `resolver_servidor` caches and maps a DNS failure to `None`.
- [ ] **T05 Adaptive slow-down** (FR-8, TR-3)
  - Tests: 429 from 2 hosts of one server within 10 min halves the ceiling
    once and logs it; 429s from 1 host do not; the floor is 35; `reducoes`
    lists the change.

## Phase C: The pool and the flows

- [ ] **T06 `execucao.por_casa`** (FR-1, FR-2, FR-12, FR-13)
  - Pool, input-order results, per-house errors reported at the end, Ctrl+C
    handling, `[host]` log prefix, periodic progress line. Add `execucao` to
    layer 6.
  - `test_execucao.py` (TR-5 unit part).
- [ ] **T07 Availability test in parallel** (FR-3)
  - Tests: same table as sequential, in table order; DNS-failing house still
    one attempt.
- [ ] **T08 New/resume pipeline per house** (FR-1, FR-9, FR-11)
  - `busca.buscar_casa`, links grouped per house, matters and downloads per
    house, links file rebuilt at the end, `downloads.preencher_downloads`.
  - Tests: 1 vs 8 workers give identical final tables (except `raspada_em`),
    same state contents, same downloads (TR-4); resume after a partial run;
    spec 2 project resumes.
- [ ] **T09 Update mode and authors/procedure on the pool** (FR-4)
  - Tests: 1 vs 8 workers equivalence for both; resume of option 3 under
    workers.
- [ ] **T10 Summary additions** (FR-14)
  - Elapsed time, workers, per-server ceiling and reductions.

## Phase D: Concurrency proof, end-to-end, docs

- [ ] **T11 Limits under threads and end-to-end** (TR-2, TR-5, TR-8)
  - `test_concorrencia.py` (second part): real threads, 0.2 s window, several
    hosts on one server; from `ao_reservar` times, no host above its limit
    and no server above its ceiling in any window.
  - `test_ponta_a_ponta.py` with 8 workers: limits per site and per server,
    interruption in the middle and resume.
- [ ] **T12 Docs** (NFR-4)
  - README (parallel run, `paralelo` in `config.json`, server ceiling and
    why), tech-stack, ROADMAP (Phase 2 ticks, new time estimate, the 1 404
    houses / shared servers finding), project site "Quanto tempo leva?".

## Phase E: Validation and merge

- [ ] **T13 Update `validation.md`** to match what was built.
- [ ] **T14 Run validation** (including the ramp), set the final defaults from
  its numbers, record the results, fix what fails, then merge into `main`.

## Traceability

| Requirement | Tasks | Tests |
|---|---|---|
| FR-1, FR-2 | T06, T08 | `test_execucao`, `test_principal` |
| FR-3 | T07 | `test_casas`, `test_principal` |
| FR-4 | T09 | `test_principal`, `test_autoria` |
| FR-5 | (unchanged) | `test_cliente_http` |
| FR-6, FR-7 | T04 | `test_cliente_http` |
| FR-8 | T05 | `test_cliente_http` |
| FR-9, FR-11 | T08 | `test_principal`, `test_ponta_a_ponta` |
| FR-10 | T02 | `test_concorrencia` |
| FR-12 | T03, T06 | `test_cliente_http`, `test_execucao`, `test_ponta_a_ponta` |
| FR-13 | T06 | `test_execucao`, `test_registro` |
| FR-14 | T10 | `test_registro`, `test_principal` |
| FR-15, FR-16 | T01 | `test_padroes`, `test_principal` |
| TR-1 | T04 | `test_cliente_http` |
| TR-2 | T11 | `test_concorrencia` |
| TR-3 | T05 | `test_cliente_http` |
| TR-4 | T08, T09 | `test_principal` |
| TR-5 | T06, T11 | `test_execucao`, `test_ponta_a_ponta` |
| TR-6 | T02 | `test_concorrencia` |
| TR-7 | T01 | `test_padroes`, `test_principal` |
| TR-8 | T11 | `test_ponta_a_ponta` |
| NFR-1 | all | review (no new dependency in `pyproject.toml`) |
| NFR-2 | T08, T09 | `test_compat_fase1` |
| NFR-4 | T12 | review |
