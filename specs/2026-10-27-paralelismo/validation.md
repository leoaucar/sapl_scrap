# Validation: Parallel runs (several houses at once)

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Tasks:** [tasks.md](tasks.md)
- **Status:** Passed (2026-10-29)
- **Run by / date:** Claude Code with the user, 2026-10-29

Checks on the implementation branch after T01–T13, against the real sites.
They cover the acceptance criteria in spec §8. Only **one program** runs at a
time (two processes would each have their own limiter).

The request counts come from the DEBUG lines of the client in `logs/*.log`
(the spec 2 validation script), plus a DNS lookup to group hosts by server.
The request lines keep their spec 2 format: the `[host]` prefix of T06 is not
added to `sapyl.http` lines, so both scripts read them unchanged.

Projects with non-default `paralelo` values are created with the defaults
changed for that one run, so `config.json` gets them before any request:

```bash
.venv/bin/python -c "import sapyl.padroes as p; p.CASAS_AO_MESMO_TEMPO = 1; \
from sapyl.interface.principal import executar; executar()"
```

(`p.LIMITE_POR_SERVIDOR = 175` for §3.) A resume reads the saved values, so
later runs of the same project use plain `sapyl`.

Server script:

```python
# limite_servidor.py <pasta do projeto>: requisições por servidor (IP) em 60 s
import collections, datetime as dt, pathlib, re, socket, sys

pasta = pathlib.Path(sys.argv[1])
pat = re.compile(
    r'^(\S+ \S+) DEBUG sapyl\.http (\S+) \| \S+ \| (\S+) \| tentativa.*?\| enviada (\S+)$'
)
envios, ips = collections.defaultdict(list), {}
for arquivo in sorted(pasta.glob('logs/*.log')):
    for linha in arquivo.read_text(encoding='utf-8').splitlines():
        m = pat.match(linha)
        if not m:
            continue
        resposta = dt.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S,%f')
        hora = dt.datetime.strptime(m.group(4), '%H:%M:%S.%f').time()
        enviada = dt.datetime.combine(resposta.date(), hora)
        if enviada > resposta:
            enviada -= dt.timedelta(days=1)
        host = m.group(2)
        if host not in ips:
            try:
                ips[host] = socket.gethostbyname(host)
            except OSError:
                ips[host] = None
        envios[ips[host]].append(enviada)
for ip, ts in sorted(envios.items(), key=str):
    ts.sort()
    i = pico = 0
    for j, t in enumerate(ts):
        while (t - ts[i]).total_seconds() >= 60:
            i += 1
        pico = max(pico, j - i + 1)
    print(f'{ip!s:16s} {len(ts):6d} req  max/60s={pico}')
```

> **Carried over from spec 2's validation** (shortened there to 9 houses on
> 2026-10-27): on the full 10 Acre houses, also check (a) `<nome>_paginas_busca.csv`
> ≥ 10× smaller than `val_a_resultados_crus_casas.csv` (§2, project `par_8`),
> and (b) option 3 on `par_8` with Ctrl+C halfway + resume and a browser spot
> check of 5 matters, Rio Branco included (§5).
>
> (a) ✅ `par_8_paginas_busca.csv` is 121 KB vs 10.0 MB for
> `val_a_resultados_crus_casas.csv` (≈ 83× smaller). (b) on a 300-matter
> sample instead of all of `par_8` (user's choice, 2026-10-30): see §5.1.

## 0. Preconditions

| # | Check | Result |
|---|---|---|
| 0.1 | Tasks T01–T13 ticked | ✅ (plus T15 from finding V1) |
| 0.2 | CI green on the branch | ✅ run 40993687180 on the last commit (`testes`, 3.10 + 3.12) |
| 0.3 | `pytest` offline < 60 s; coverage ≥ 95 % (AC 1) | ✅ time: 35 s · coverage: 99 % (349 tests; also 3.10 + pandas 2 locally) |
| 0.4 | No new dependency in `pyproject.toml` (NFR-1) | ✅ `pyproject.toml` unchanged |
| 0.5 | A hand-edited invalid `paralelo` (e.g. `limite_por_servidor: 10`) stops before any request with exit code 2 and a message naming the key | ✅ on a copy of `par_seq`: exit 2, `"paralelo.limite_por_servidor" = 10: … no mínimo 35`, 0 request lines in the new log. Cosmetic: "Buscando os termos" prints before the error (note for Phase 2b) |

## 1. Sequential reference — for AC 3

Project `par_seq`: the 10 Acre houses, the 3 keywords of the spec 2
validation, no downloads, created with `CASAS_AO_MESMO_TEMPO = 1` (command
above); check `config.json` shows `"casas_ao_mesmo_tempo": 1`.

| Check | Expected | Result |
|---|---|---|
| Finishes; 0 matters with error, or each error with a reason | yes | ✅ after one resume (finding V1): 1 301 found, 1 190 unique, 1 190 `ok`, 0 errors, 30/30 searches complete |
| Elapsed time (summary) | recorded | first run 6 min 42 s (cut short by V1) + resume 46 min 04 s (18:44–19:30) |
| Limits | ≤ 35 per host | ✅ max 35/60 s (Rio Branco, 1 586 requests in the resume; shortest 36-span 60.997 s); server max 95/60 s with one house at a time (consecutive small houses) |

## 2. Parallel run — AC 2, AC 3

Project `par_8`, same inputs, defaults (`8` houses, `120`/min per server).

| Check | Expected | Result |
|---|---|---|
| Max requests per host per 60 s (spec 2 script) | ≤ 35 | ✅ 35 (Rio Branco 1 587 requests, AL 220); shortest 36-span 60.999 s (RB), 60.979 s (AL): logged send time is a few ms after the reservation |
| Max requests per server per 60 s (script above) | ≤ 120 | ✅ exactly 120 (1 865 requests, all 10 hosts on `201.54.51.178`): the ceiling was reached and held |
| `HTTP 429` lines | 0, or a logged slow-down and no data lost | ✅ 0 (1 835 × 200, 30 × 404) |
| Same keys and statuses as `par_seq` (differences explained by site changes) | yes | ✅ 1 190 = 1 190 keys, all `ok`; every column identical except `raspada_em` |
| Final table order: houses in table order | yes | ✅ identical row order to `par_seq` |
| Terminal: `[host]` prefix on lines, overall progress line every minute | yes | ✅ `[sapl.al.ac.leg.br] Testando casa 1 de 10…`; 45 progress lines ("8 de 10 casas concluídas, 2 em andamento, 0 na fila; matérias: …") |
| Summary: elapsed time, "até 8 casas ao mesmo tempo", one line per server with its limit | yes | ✅ "Tempo: 45 min 59 s (até 8 casas ao mesmo tempo)", "Servidor 201.54.51.178 (10 casas): até 120 requisições por minuto" |
| `config.json` has `paralelo` with the defaults | yes | ✅ |
| Elapsed time vs `par_seq` | shorter; recorded | ⚠️ 46 min vs 46 min (resume of `par_seq`): no gain on this set. Rio Branco alone has 1 587 requests, ≈ 45 min at 35/min; the other 9 houses finish in the first minutes. The speed-up needs many houses with work at once (full runs), not this set. |

## 3. Ramp — AC 4

Project `par_175`: same inputs, `limite_por_servidor` = `175` (5 houses at
full speed), `casas_ao_mesmo_tempo` = `8` (command above with
`p.LIMITE_POR_SERVIDOR = 175`). Wait at least 2 minutes after `par_8` ends.

| Check | Expected | Result |
|---|---|---|
| Max per server per 60 s | ≤ 175 | ⏭️ not run |
| 429 count, median response time vs `par_8` | recorded | ⏭️ not run |
| Slow-down triggered? | recorded | ⏭️ not run |
| **Final defaults chosen** (and why, with the numbers above) | written here and in `padroes.py` | ✅ **8 houses, 120 per server** (unchanged) |

> **Skipped on 2026-10-29, at the user's request.** On these 10 houses only
> Rio Branco and AL have real work, so the server never needs more than
> ~120/min (`par_8` reached 120 only in the first minutes, while all houses
> searched) and a ceiling of 175 could not be exercised. The defaults stay at
> the conservative starting values, which `par_8` showed to be safe (0 × 429
> at the 120 ceiling). Raising them needs evidence from a run where several
> large houses work at once; that is left for a later full run.

## 4. Interruption — AC 5

During a new parallel run (`par_int`), press Ctrl+C when about half of the
matters are done; then resume.

| Check | Expected | Result |
|---|---|---|
| Exits within 30 s, with the resume message, no traceback | yes | ✅ 0.14 s (SIGINT at 20:47:33, Rio Branco matter 341 of 1 010, 521 of 1 190 `ok`); "Parando: esperando 1 casa(s)…" then the resume message, no traceback |
| Resume finishes; only in-flight items requested twice (log) | yes | ✅ 0 of the 521 `ok` matters scraped again, 0 search pages; the one `materialegislativa/21081/` request in the resume log is the title lookup of an attached matter (not yet in the cache), not a re-scrape. 21 min 06 s, 1 timeout retried |
| Same keys as `par_seq` | yes | ✅ 1 190 = 1 190, same order, same statuses (all `ok`); limits: host ≤ 35, server ≤ 120 over both runs |

## 5. Update and authors/procedure in parallel — AC 6

On `par_8`: update mode (no `Relevante`), then option 3.

| Check | Expected | Result |
|---|---|---|
| Update: same keys, statuses `ok`, limits held | yes | ✅ `par_8_resultado_final_ATUALIZADO_29_10_2026.csv`: 1 190 rows, same keys and order, all `ok`, 28 min 58 s (21:09–21:38); 1 190 requests (names from the cache), host ≤ 35/60 s, server ≤ 70/60 s, 0 × 429 |
| Option 3: `Autoria`/`Tramite` filled, `fonte_autoria` = `api`, limits held | yes | ✅ on the updated table: 1 190 `ok` / 1 190 `ok`, 0 errors, 1 h 01 min 45 s (21:38–22:40); `fonte_autoria` 1 189 `api`, 1 `api+html` (an isolated 404 on one list, as in spec 2); 2 564 requests, host ≤ 35/60 s, server ≤ 70/60 s, 0 × 429. Empty `Autoria` 62 / `Tramite` 376 (Rio Branco 61/363, AL 1/13): spot-checked RB 27827 and 41321, the API and the HTML page have no procedure entries |

### 5.1 Option 3 with Ctrl+C and resume (carried over from spec 2, item b)

Added on 2026-10-30. Input: a CSV with the first 150 matters of each house in
`par_int_resultado_final.csv` (AL and Rio Branco, 300 matters), in
`val_autoria_proj/`, through option 3 with a CSV path (no project cache).
SIGINT sent by a script at 14:52:35; then a resume. Reference: the same
input run once without interruption (`val_autoria_run_sem_ctrlc_proj/`,
10 min 16 s). (A first attempt at the interruption did not stop: the
script started the program with SIGINT ignored, a property of background
jobs in non-interactive bash; fixed with `set -m`, not a program issue.)

| Check | Expected | Result |
|---|---|---|
| Ctrl+C stops quickly, resume message, no traceback | yes | ✅ under 1 s at 105 of 300 (AL 48, RB 57); "Parando: esperando 2 casa(s)…", exit code 1, no traceback |
| Resume skips what is done; only in-flight items requested twice | yes | ✅ "195 matérias a buscar, 105 já feitas"; 1 matter in both logs (AL 16733: its `autoria` request was sent at 14:52:16, before the stop, and it was not yet in the state file); 7 min 10 s |
| Same result as an uninterrupted run | yes | ✅ 300 rows, same order; `Autoria`, `Tramite`, statuses, `fonte_autoria`, `erro` identical; 300 `ok` / 300 `ok`, `fonte_autoria` all `api` |
| Limits over both runs | host ≤ 35, server ≤ 120 | ✅ AL 35, RB 35, server 70 per 60 s; 744 requests, all 200 |
| Browser spot check of 5 matters (Rio Branco included) | `Autoria` and latest `Tramite` match the site | ✅ AL 16733, 16055, 3693; RB 38704, 42362 (empty `Tramite`, none on the site either): all match (checked by the user) |

## 6. Docs

| Check | Expected | Result |
|---|---|---|
| README explains the parallel run, `paralelo` and the server ceiling | yes | ✅ "Várias casas ao mesmo tempo", summary and log, code layout (T12) |
| ROADMAP Phase 2 ticked, time estimate updated | yes | ✅ 1 404 houses / shared server finding, 3–6 h estimate (T12) |
| Project site "Quanto tempo leva?" updated | yes | ✅ paragraph on 8 houses and the 120/min server ceiling (T12) |

## 7. Larger ramp — is a higher server ceiling worth it, and safe?

Added on 2026-10-29 at the user's request, because §3 could not exercise the
ceiling on the 10 Acre houses. Run last, after §1–§6.

**Inputs.** The first 50 houses of the list (option `2`: AC, AL, AM, AP, with
capitals and state assemblies), the education keyword list
(`exemplo_palavras_chave_educacao.csv` copied to `palavras_chave.csv`, 23
searches per house, so most houses are busy at the same time), no downloads,
`casas_ao_mesmo_tempo` = 8.

**Runs.** Two projects, same day, one after the other with at least 5 minutes
between them, each stopped with Ctrl+C after **30 minutes** (the ramp measures
load, not completion; the Ctrl+C is also a second check of §4):

1. `ramp_120`: `limite_por_servidor` = 120 (default).
2. `ramp_175`: `limite_por_servidor` = 175 (command at the top with
   `p.LIMITE_POR_SERVIDOR = 175`).

**Measures** (from the logs, per server and per minute): requests, `HTTP 429`
(and from how many hosts), slow-downs logged, response time (log line time
minus send time) median and 95th percentile, timeouts and 5xx; requests to
search pages and matters done in the 30 minutes.

| Check | `ramp_120` | `ramp_175` |
|---|---|---|
| Max requests per server per 60 s (`201.54.51.178`, 40 houses) | 120 | 175 |
| Minutes at the ceiling (≥ 95 % of it) | 18 (22:41–22:58) | 12 (23:16–23:27) |
| `HTTP 429` (hosts) / slow-downs | 0 / 0 | 0 / 0 |
| Response time median / p95 (s) | 0.08 / 0.33 | 0.07 / **0.51** (per minute up to 0.77, 23:22–23:26) |
| Timeouts / 5xx | 0 / 0 | 0 / 0 |
| Requests on the shared server (whole run) | 2 223 | 2 224 |
| Whole run (both finished before 30 min, so no Ctrl+C) | 20 min 31 s | 16 min 40 s |
| Results | 416 matters `ok`, 966 searches (2 incomplete: site 404 on page 1) | same 416 keys, order and statuses (1 incomplete search, same site quirk) |

Other servers seen: `201.54.51.179` (1 house) and `159.60.67.5` (1 house,
another provider), each ≤ 35/60 s. 8 of the 50 houses no longer exist in DNS.

**Decision rule.** Raise the default to 175 only if, in `ramp_175`: the
ceiling was actually reached for several minutes (otherwise inconclusive), 0 ×
429 and no slow-down, no rise in timeouts/5xx, and the median and p95 response
times are at most 1.5× those of `ramp_120`. Otherwise keep 120. Record the
decision here, in `padroes.py` and in the README/ROADMAP if it changes.

| Decision | Why (numbers) |
|---|---|
| **Keep 120** (defaults unchanged: 8 houses, 120 per server) | The ceiling of 175 was reached for 12 minutes with 0 × 429, no slow-down and no timeouts/5xx, and the median did not change, but the p95 response time rose from 0.33 s to 0.51 s (1.55×, above the 1.5× rule), with per-minute p95 up to 0.77 s: a mild sign of strain on the shared server. The gain was 3 min 51 s (19 %) on this run. Revisit with a full run if speed becomes a problem; 150 would be the next step to try. |

## 8. Result

| Acceptance criterion (spec §8) | Section | Result |
|---|---|---|
| 1. Offline suite, CI, coverage | 0 | ✅ |
| 2. Limits per site and per server | 2 | ✅ |
| 3. Same keys as sequential | 1, 2 | ✅ identical tables |
| 4. Ramp and final defaults | 3, 7 | ✅ §3 skipped (set too small), §7 run: keep 120 |
| 5. Ctrl+C and resume | 4 | ✅ |
| 6. Update and option 3 in parallel | 5 | ✅ |

**Issues found** (each becomes a task in `tasks.md`):

| # | Description | Task | Fixed and re-checked |
|---|---|---|---|
| V1 | A one-minute loss of DNS on this machine (18:40–18:41, first `par_seq` run) made every later request fail at once with `dns`, which is never retried: 9 houses lost in one second | T15 | ✅ `dns` from a site that already answered in the run is now retried as `conexao` (tests); the runs after it (`par_8`, `par_int`, update, option 3, ramps) had no `dns` error on a working house |
| — | Notes, no fix: (a) on the 10 Acre houses the parallel run is not faster (Rio Branco alone bounds it); the gain shows with many houses with work, as in §7. (b) "Buscando os termos" prints before the `paralelo` error (cosmetic, for Phase 2b). (c) A search interrupted by Ctrl+C restarts from page 1 on resume (per house and keyword); resuming from the last page is a Phase 2b / later idea. | — | — |

**Decision:** ☒ merge into `main` ☐ fix and re-run

**Notes:** runs on 2026-10-29 18:34–23:33, one program at a time, from this
machine. Validation projects `par_seq`, `par_8`, `par_int`, `ramp_120`,
`ramp_175` stay untracked on disk.
