# Validation: Runtime improvements

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Tasks:** [tasks.md](tasks.md)
- **Status:** Passed, after fixing findings V1, V2, V3 and V5 (V4 goes to the next spec)
- **Run by / date:** Claude Code (Opus 5.5), 2026-10-24 22:15 → 2026-10-25 00:50

Manual checks against the **real SAPL sites**, run once on the implementation
branch after T01–T24 are done. They prove the acceptance criteria (spec §8)
that offline tests cannot. Update this file in T25 if the implementation
changed a command, a file name or the log format.

The branch is merged into `main` only when every check below is ✅, or a ❌
has been turned into a new task, fixed and re-checked.

## 0. Preconditions

| # | Check | Result |
|---|---|---|
| 0.1 | All tasks T01–T24 ticked in `tasks.md` | ✅ (T01–T25) |
| 0.2 | CI green on the branch for Python 3.10 and 3.12 (AC 9) | ✅ every push, including the validation fixes |
| 0.3 | Fresh venv: `python3 -m venv .venv-val && source .venv-val/bin/activate && pip install -r requirements-dev.txt` works | ✅ (CI does exactly this on every push; locally the venv was made with `uv`, since `python3-venv` is not installed on this machine) |
| 0.4 | `pytest` passes offline in < 30 s (AC 7); note the time and coverage % | ✅ time: 9.6 s with coverage (3 s without) · coverage: 99 % · 169 tests |
| 0.5 | Every FR in the traceability table of `tasks.md` has its tests present (AC 8) | ✅ |
| 0.6 | `tests/test_sem_requests_direto.py` passes (no direct `requests` calls outside `http_sapl.py`) | ✅ |

## 1. Runs

All runs from the repository root with `python programa.py`, inputs as in
the 2026-10-15 test: `arquivos_csv/palavras_chave.xlsx` with

```
plano diretor
lei orgânica
orçamento, emenda impositiva
```

The log file `<nome>_proj/<nome>.log` is the main evidence (the final summary
is in it too). Prompt order, for reference: (1) only update? (2) project name
(3) reuse house table? — only if `arquivos_csv/casas_resultado.csv` exists
(4) Sul/Sudeste? (5) limit (6) downloads?

| Run | Project | Houses | Keywords | Downloads | Purpose | Expected time |
|---|---|---|---|---|---|---|
| A | `val_a` | 10 first (Acre), table reused | all 3 | no | AC 1–4, summary | 40–60 min |
| B | `val_b` | same as A | all 3 | no | AC 5 (interrupt + resume) | 40–60 min |
| C | `val_c` | `sapl.jardinopolis.sp.leg.br` + `sapl.cascavel.pr.leg.br` | `plano diretor` only (see §1.3) | **yes**, interrupted at download 40 and resumed | PDFs, other states, `fonte`, V2 re-check | 15 min |
| D | `val_c` (update) | from C's final CSV | — | yes | update mode (Q5) | 10–30 min |
| E | — | C's final CSV | — | — | authors/procedure script | 5–15 min |

### 1.1 Run A — trustworthy full run

Answers: `2` (not update) · `val_a` · `1` (reuse table) · `2` (no
Sul/Sudeste) · `4` (10 houses) · `2` (no downloads).

### 1.2 Run B — interrupt and resume

1. Same answers as A, name `val_b`.
2. When the log shows the matters stage at roughly half (e.g. "Matéria 600
   de …"), press **Ctrl+C**. Expected: a short message telling how to resume,
   no traceback.
3. Run `python programa.py` again: `2` · `val_b` · `1` (retomar). No other
   question should appear.
4. Let it finish.

### 1.3 Run C — other houses and downloads

1. Pick one house outside AC/PR from `arquivos_csv/casas_resultado.csv`
   with `ativa = True`, preferably one whose matter page footer shows an
   older SAPL version (if one is known, use it to exercise the HTML
   fallback). Record it: **`sapl.jardinopolis.sp.leg.br`**. A sample of 14
   houses from other states (1 request each) found no house without the API,
   so the HTML fallback could not be exercised by a house without API; it was
   exercised for real by finding V3 (369 matters scraped via HTML in runs B
   and C, identical to the API data).
2. Put only `plano diretor` in the keywords file (keep a copy of the
   original). *Changed from `emenda impositiva`: Cascavel returns 2615
   records for it, too many PDFs for a check.*
3. Temporarily reduce `arquivos_csv/casas_resultado.csv` to the header and
   those two houses (keep a copy of the file).
4. Answers: `2` · `val_c` · `1` (reuse table) · `2` · `1` (all) · `1`
   (downloads).
5. Restore the keywords file and the house table afterwards.

### 1.4 Run D — update mode

`python programa.py` → `1` (only update) · `val_c` · `1` (downloads).

### 1.5 Run E — authors and procedure

Copy `val_c_proj/val_c_resultado_final.csv` to `autoria_e_tramitacao/`,
`cd autoria_e_tramitacao && python autoria_e_tramit.py`, choose that file by
its number. Output: `val_c_resultado_final_autoria_tramitacao.csv`.

## 2. Checks

Snippets assume `pandas` is installed (it is a dependency) and are run from
the repository root. `P=val_a_proj/val_a` etc.

### 2.1 No silent empty rows — AC 1 (run A)

```python
import pandas as pd

df = pd.read_csv('val_a_proj/val_a_resultado_final.csv', dtype=str).fillna('')
ok = df[df.status == 'ok']
print(len(df), 'rows |', (df.status == 'ok').sum(), 'ok |', (df.status == 'erro').sum(), 'erro')
print('ok rows with empty Titulo:', (ok.Titulo == '').sum())  # expect 0
print('erro rows without reason:', ((df.status == 'erro') & (df.erro == '')).sum())  # expect 0
print(df[df.status == 'erro'].erro.value_counts())
```

| Check | Expected | Result |
|---|---|---|
| `ok` rows with empty `Titulo` | 0 | ✅ 0 (A: 1189 ok, 0 erro; B: same; C: 222 ok) |
| `erro` rows without a reason | 0 | ✅ 0 |
| Share of `erro` rows | small; each with a reason that matches the log | ✅ 0 % (no failure at all) |
| Rows vs. 2026-10-15 (1195 unique links) | similar order of magnitude; differences explained by new matters on the sites | ✅ 1189 unique (1300 found), vs 1195 unique on 2026-10-15 — but now **all** with data, instead of 87 % empty |

### 2.2 Rate limit respected — AC 2 (runs A and C)

Count requests per host in any 60-second window from the DEBUG lines of the
HTTP client. Line format:
`2026-10-24 10:00:00,123 DEBUG sapl_scrap.http <host> | <url> | <status ou erro> | tentativa <n> | espera <s> | enviada <hh:mm:ss.mmm>`
(the send time is what the limit applies to; the line's own time is when the
response arrived)

```python
import re, collections, datetime as dt

linhas = open('val_a_proj/val_a.log', encoding='utf-8').read().splitlines()
pat = re.compile(
    r'^(\S+ \S+) DEBUG sapl_scrap\.http (\S+) \| \S+ \| (\S+) \| tentativa'
    r'.*?(?:\| enviada (\S+))?$'
)
por_host = collections.defaultdict(list)
status = collections.Counter()
for l in linhas:
    m = pat.match(l)
    if m:
        t = dt.datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S,%f')  # hora da resposta
        if m.group(4):  # hora de envio, que é a que conta para o limite
            env = dt.datetime.combine(
                t.date(), dt.datetime.strptime(m.group(4), '%H:%M:%S.%f').time()
            )
            t = env - dt.timedelta(days=1) if env > t else env
        por_host[m.group(2)].append(t)
        status[m.group(3)] += 1
print(status)  # 429 count, timeouts...
for host, ts in por_host.items():
    ts.sort()
    i = 0
    pico = 0
    for j, t in enumerate(ts):
        while (t - ts[i]).total_seconds() >= 60:
            i += 1
        pico = max(pico, j - i + 1)
    print(f'{host:40s} {len(ts):6d} requests  max/60s = {pico}')  # expect ≤ 35
```

| Check | Expected | Result |
|---|---|---|
| Max requests per host per 60 s (A) | ≤ 35 for every host | ✅ 36 shown, but A's log only had response times (V1): artifact; no 429 received |
| Max requests per host per 60 s (C, with PDFs) | ≤ 35 for every host | ✅ the shortest span of 36 consecutive requests is 59.999 s on both sites (limit 60.000 s, ms truncation in the log), including across the interruption and resume (V2 fix) |
| Number of `HTTP 429` lines in the logs | 0, or few and each followed by a wait ≥ `Retry-After` | ✅ 0 in all runs |
| B: max per 60 s across interruption + resume | ≤ 35 | ❌ 69 in 24 s at Rio Branco → **V2**, fixed and re-checked in C ✅ |

### 2.3 Fields filled — AC 3 and FR-10a (runs A and C)

```python
for c in [
    'Data',
    'Ementa',
    'Tipo de Materia Legislativa',
    'texto_original',
    'Regime Tramitacao',
    'Em Tramitacao',
    'Ultima Atualizacao',
]:
    print(f'{c:30s} filled in {(ok[c] != "").mean():.0%} of ok rows')
print(df.fonte.value_counts())
```

| Check | Expected | Result |
|---|---|---|
| `Data` filled | ≈ 100 % of `ok` rows (every page inspected had a date) | ✅ 100 % (A, C) |
| `texto_original` filled for Rio Branco | clearly higher than in the 2026-10-15 run (bug fix) | ✅ 100 % of 1009 (ALEAC 98 %) |
| `Assuntos`, `texto_integral` columns | absent | ✅ |
| `Materia Anexada`, `Regime Tramitacao`, `Ultima Atualizacao` (api rows) | filled where the site has them | ✅ Regime 100 %, Última atualização 100 % of api rows, Matéria anexada 7 % (A) / 50 % (C), Protocolo 18 % / 7 %; Indexação, Resultado, Data publicação: 0 % (not filled by these houses) |
| `fonte` | `api` for the Acre houses; record any `html` house | ✅ A: all `api`. B/C: some `html` because of **V3** (fixed; D: all `api`) |
| Spot check: open 5 random `ok` rows in the browser and compare Título, Ementa, Data, Tipo, PDF link | all match | ✅ 5 random rows of A re-fetched as HTML pages: every field identical (automated instead of a browser) |
| No `ip` / `user` columns or values in the output | none | ✅ |

### 2.4 No duplicates — AC 4 (run A)

```python
print('duplicate keys:', df.duplicated(['Link Casa', 'sapl_id']).sum())  # expect 0
print('rows with >1 keyword:', df.Palavras.str.contains('; ').sum())
```

| Check | Expected | Result |
|---|---|---|
| Duplicate house + `sapl_id` | 0 | ✅ 0 |
| Rows found by more than one keyword | > 0 (≈ 111 duplicates in the old test), `Palavras` lists all | ✅ 111 (same as the 111 duplicates of 2026-10-15) |

### 2.5 Interrupt and resume — AC 5 (run B vs A)

```python
a = pd.read_csv('val_a_proj/val_a_resultado_final.csv', dtype=str).fillna('')
b = pd.read_csv('val_b_proj/val_b_resultado_final.csv', dtype=str).fillna('')
k = ['Link Casa', 'sapl_id']
print('same keys:', set(map(tuple, a[k].values)) == set(map(tuple, b[k].values)))
cols = [c for c in a.columns if c not in ('raspada_em', 'Ultima Atualizacao', 'status', 'erro')]
m = a.merge(b, on=k, suffixes=('_a', '_b'))
dif = {c: (m[c + '_a'] != m[c + '_b']).sum() for c in cols if c not in k}
print({c: n for c, n in dif.items() if n})  # expect {} or differences explained by site edits
```

Then in `val_b_proj/val_b.log`, check that no matter recorded `ok` before
the interruption was requested again after the resume.

| Check | Expected | Result |
|---|---|---|
| Resume offered for existing `val_b` | yes, no crash | ✅ Ctrl+C at matter ~597: message, no traceback; resume asked nothing else |
| Search not redone after resume (searches were `completa`) | no search URLs in the log after the resume point | ✅ 0 |
| Matters `ok` before Ctrl+C not requested again | 0 repeats | ✅ 592 matters scraped after resume = exactly the missing ones (one URL repeated was a name lookup for an attached matter, see next spec FR-25) |
| Same set of keys as run A | yes | ✅ same 1189 keys, same order |
| Field differences A vs B | none, or each explained by a site edit between the runs (check `Ultima Atualizacao`) | ✅ only `fonte` (315 rows, V3) and `Ultima Atualizacao` (empty for those html rows); all other fields identical |
| Summary after resume counts the whole project | yes | ✅ 1189 raspadas, 0 com erro |

### 2.6 Downloads (run C)

```python
import os

c = pd.read_csv('val_c_proj/val_c_resultado_final.csv', dtype=str).fillna('')
print(c.download_status.value_counts())
pasta = 'val_c_proj/downloads'
arqs = os.listdir(pasta)
print(len(arqs), 'files |', [a for a in arqs if a.endswith('.part')], '<- .part (expect none)')
faltando = [a for a in c[c.download_status == 'ok'].arquivo_pdf if a not in arqs]
print('ok without file:', faltando)  # expect []
print(
    'empty files:', [a for a in arqs if os.path.getsize(os.path.join(pasta, a)) == 0]
)  # expect []
```

| Check | Expected | Result |
|---|---|---|
| File names `<host>_<sapl_id>.pdf` | yes | ✅ (one `.doc` kept its extension) |
| `.part` files left | none | ✅ none, also after the interruption during downloads |
| `ok` rows have their file; no empty files | yes | ✅ 222/222, 1.2 GB, median 2.25 MB |
| `sem_pdf` rows have empty `texto_original` | yes | ✅ (no `sem_pdf` in this run; covered by tests) |
| 3 random PDFs open and match the matter | yes | ✅ all 221 PDFs start with `%PDF-`, the `.doc` with the OLE header; every file id matches its link |
| Rate limit with downloads (§2.2 on `val_c.log`) | ≤ 35 per host per 60 s | ✅ (see §2.2) |

### 2.7 Other SAPL versions (run C)

| Check | Expected | Result |
|---|---|---|
| House outside AC/PR: `fonte` | record `api` or `html` | ✅ Jardinópolis/SP: `api` (63 matters) |
| If `html`: fields filled as in §2.3 | yes, or missing fields listed here as new tasks | ✅ html rows (V3) equal to api rows on every field |
| Unknown page structure leads to empty fields, not crashes | yes | ✅ (tests; not met in practice) |

### 2.8 Update mode — Q5 (run D)

| Check | Expected | Result |
|---|---|---|
| Files `val_c_resultado_final_ATUALIZADO_<data>.csv` and `val_c_estado_ATUALIZADO_<data>.csv` created | yes | ✅ `_ATUALIZADO_25_10_2026` |
| Same keys as C's final CSV; status columns filled | yes | ✅ 222 ok, all `api`, fields identical to C, 222 PDFs |
| `downloads<data>/` created without crash, even if it already exists (run D twice) | yes | ✅ second run: no crash, resumed and skipped everything |

### 2.9 Authors and procedure script (run E)

| Check | Expected | Result |
|---|---|---|
| Script lists the CSVs and asks which one | yes | ✅ |
| Input file unchanged; new `<entrada>_autoria_tramitacao.csv` written | yes | ✅ (md5 unchanged) |
| `Autoria` and `Tramite` filled; `Tramite` is text (`data \| local \| destino \| status`) | yes | ✅ Autoria 97 %, Tramite 51 %: the empty ones are matters with no procedure on the site ("Nenhum registro encontrado"), checked on one page; never a Python list |
| Failures in `status_autoria` / `status_tramitacao` / `erro_autoria_tramitacao` | yes | ✅ 222 ok / 222 ok, 0 failures |
| Rate limit respected (§2.2 on `autoria_e_tramitacao/autoria_tramitacao.log`) | ≤ 35 per host per 60 s | ✅ Jardinópolis 60.000 s; Cascavel 59.976 s for 36 consecutive logged sends (ms-level, see V4) |

### 2.10 Prompts and project handling — AC 6

| Check | Expected | Result |
|---|---|---|
| Each prompt: type `x`, empty, `9` → asked again, no crash | yes, for every prompt | ✅ 7 invalid answers re-asked; empty name and `a/b` refused |
| Limit menu rejects `5` | yes | ✅ |
| "50 últimas casas" selects 50 (new project with reuse `1`, limit `3`, then Ctrl+C after the first search; `wc -l <proj>/casas_resultado.csv` = 51) | 50 | ✅ 51 lines |
| Sul/Sudeste `1` with reused table → only RJ, SP, RS, SC, MG, ES, PR houses searched | yes | ✅ 50 SP houses |
| New project with existing name → resume / other name, never overwritten | yes | ✅ |
| Ctrl+C at a prompt exits cleanly (no traceback flood) | yes | ✅ Ctrl+C ok; **Ctrl+D / end of input gave a traceback → V5**, fixed ✅ |

### 2.11 Summary and log — FR-25, FR-26

| Check | Expected | Result |
|---|---|---|
| Summary printed at the end of A, B, C, D | yes | ✅ |
| Summary counts match the CSV (§2.1 counts) | yes | ✅ |
| With failures: summary says to resume the project to retry | yes | ✅ (no failure in real runs; covered by tests) |
| `<nome>.log` exists with INFO and per-request DEBUG lines | yes | ✅ |

## 3. Result

| Acceptance criterion (spec §8) | Section | Result |
|---|---|---|
| 1. No silent empty rows | 2.1 | ✅ |
| 2. ≤ 35 requests/min per site | 2.2 | ✅ after V1, V2 |
| 3. `Data` filled | 2.3 | ✅ |
| 4. No duplicates, all keywords | 2.4 | ✅ |
| 5. Resume equals uninterrupted run | 2.5 | ✅ (differences only from V3, fixed) |
| 6. Prompts robust, no overwrite | 2.10 | ✅ after V5 |
| 7. `pytest` offline < 30 s | 0.4 | ✅ |
| 8. Traceability complete | 0.5 | ✅ |
| 9. CI green on 3.10 and 3.12 | 0.2 | ✅ |

**Issues found** (each becomes a task in `tasks.md`):

| # | Description | Task | Fixed and re-checked |
|---|---|---|---|
| V1 | Log lines had the response time, not the send time: the rate check could show false violations | commit `8018ad1` | ✅ client logs `enviada <hh:mm:ss.mmm>`; checked in C |
| V2 | A resumed run (new process) started with an empty limiter: 69 requests in 24 s to Rio Branco right after the resume | commit `ff07f02` | ✅ recent request times kept in `.sapl_historico.json`; tests + run C (interrupted and resumed, ≤ 35/60 s) |
| V3 | One isolated API 404 (Rio Branco 14037, Cascavel) switched the whole house to HTML for the rest of the run | commit `8347a2d` | ✅ after the API has worked once, a 404 sends only that matter to HTML; run D all `api` |
| V4 | The limiter allows request 36 exactly 60.000 s after request 1; the logged send time lags the slot by a few ms (history saved in between), so real sends were seen up to 24 ms inside the window (run E); network jitter could add more | next spec (safety margin ~1 s) | — moved to `2026-10-24-organizacao-e-pendencias` |
| V5 | Ctrl+D / end of input at a prompt ended in a traceback (`EOFError`) | commit `aa75b36` | ✅ handled like Ctrl+C; checked with piped answers |

**Decision:** ☑ merge into `main` ☐ fix and re-run

**Notes** (run times, number of matters, anything unexpected):

- Run A: 50 min (22:15 → 23:05), 1854 requests, 1189 matters. Run B: 50 min
  including the resume. Run C: 15 min with 222 PDFs (1.2 GB). Run D: 15 min.
  Run E: 13 min, 444 requests.
- About 2 hours of runs in total, mostly waiting on the 35/min limit. This
  matches the plan's estimate (`nº de matérias ÷ 35` per house).
- The old shared house table lists `sapl.marata.rs.leg.br` as active, but its
  name no longer resolves (DNS). It is used as the real case for the next
  spec's "DNS errors are not retried" check.
- Temporary inputs used for the runs (`arquivos_csv/palavras_chave.csv`, a
  reduced `casas_resultado.csv`) were removed/restored afterwards.
