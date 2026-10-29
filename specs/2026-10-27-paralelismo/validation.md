# Validation: Parallel runs (several houses at once)

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Tasks:** [tasks.md](tasks.md)
- **Status:** Not run
- **Run by / date:** _fill in_

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

## 0. Preconditions

| # | Check | Result |
|---|---|---|
| 0.1 | Tasks T01–T13 ticked | |
| 0.2 | CI green on the branch | |
| 0.3 | `pytest` offline < 60 s; coverage ≥ 95 % (AC 1) | time: ___ s · coverage: ___ % |
| 0.4 | No new dependency in `pyproject.toml` (NFR-1) | |
| 0.5 | A hand-edited invalid `paralelo` (e.g. `limite_por_servidor: 10`) stops before any request with exit code 2 and a message naming the key | |

## 1. Sequential reference — for AC 3

Project `par_seq`: the 10 Acre houses, the 3 keywords of the spec 2
validation, no downloads, created with `CASAS_AO_MESMO_TEMPO = 1` (command
above); check `config.json` shows `"casas_ao_mesmo_tempo": 1`.

| Check | Expected | Result |
|---|---|---|
| Finishes; 0 matters with error, or each error with a reason | yes | |
| Elapsed time (summary) | recorded | ___ min |

## 2. Parallel run — AC 2, AC 3

Project `par_8`, same inputs, defaults (`8` houses, `120`/min per server).

| Check | Expected | Result |
|---|---|---|
| Max requests per host per 60 s (spec 2 script) | ≤ 35 | |
| Max requests per server per 60 s (script above) | ≤ 120 | |
| `HTTP 429` lines | 0, or a logged slow-down and no data lost | |
| Same keys and statuses as `par_seq` (differences explained by site changes) | yes | |
| Final table order: houses in table order | yes | |
| Terminal: `[host]` prefix on lines, overall progress line every minute | yes | |
| Summary: elapsed time, "até 8 casas ao mesmo tempo", one line per server with its limit | yes | |
| `config.json` has `paralelo` with the defaults | yes | |
| Elapsed time vs `par_seq` | shorter; recorded | ___ min vs ___ min |

## 3. Ramp — AC 4

Project `par_175`: same inputs, `limite_por_servidor` = `175` (5 houses at
full speed), `casas_ao_mesmo_tempo` = `8` (command above with
`p.LIMITE_POR_SERVIDOR = 175`). Wait at least 2 minutes after `par_8` ends.

| Check | Expected | Result |
|---|---|---|
| Max per server per 60 s | ≤ 175 | |
| 429 count, median response time vs `par_8` | recorded | |
| Slow-down triggered? | recorded | |
| **Final defaults chosen** (and why, with the numbers above) | written here and in `padroes.py` | |

## 4. Interruption — AC 5

During a new parallel run (`par_int`), press Ctrl+C when about half of the
matters are done; then resume.

| Check | Expected | Result |
|---|---|---|
| Exits within 30 s, with the resume message, no traceback | yes | ___ s |
| Resume finishes; only in-flight items requested twice (log) | yes | |
| Same keys as `par_seq` | yes | |

## 5. Update and authors/procedure in parallel — AC 6

On `par_8`: update mode (no `Relevante`), then option 3.

| Check | Expected | Result |
|---|---|---|
| Update: same keys, statuses `ok`, limits held | yes | |
| Option 3: `Autoria`/`Tramite` filled, `fonte_autoria` = `api`, limits held | yes | |

## 6. Docs

| Check | Expected | Result |
|---|---|---|
| README explains the parallel run, `paralelo` and the server ceiling | yes | |
| ROADMAP Phase 2 ticked, time estimate updated | yes | |
| Project site "Quanto tempo leva?" updated | yes | |

## 7. Result

| Acceptance criterion (spec §8) | Section | Result |
|---|---|---|
| 1. Offline suite, CI, coverage | 0 | |
| 2. Limits per site and per server | 2 | |
| 3. Same keys as sequential | 1, 2 | |
| 4. Ramp and final defaults | 3 | |
| 5. Ctrl+C and resume | 4 | |
| 6. Update and option 3 in parallel | 5 | |

**Issues found** (each becomes a task in `tasks.md`):

| # | Description | Task | Fixed and re-checked |
|---|---|---|---|
| | | | |

**Decision:** ☐ merge into `main` ☐ fix and re-run

**Notes:**
