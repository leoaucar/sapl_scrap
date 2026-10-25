# Validation: Runtime improvements

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Tasks:** [tasks.md](tasks.md)
- **Status:** Not run
- **Run by / date:** _fill in_

Manual checks against the **real SAPL sites**, run once on the implementation
branch after T01–T24 are done. They prove the acceptance criteria (spec §8)
that offline tests cannot. Update this file in T25 if the implementation
changed a command, a file name or the log format.

The branch is merged into `main` only when every check below is ✅, or a ❌
has been turned into a new task, fixed and re-checked.

## 0. Preconditions

| # | Check | Result |
|---|---|---|
| 0.1 | All tasks T01–T24 ticked in `tasks.md` | |
| 0.2 | CI green on the branch for Python 3.10 and 3.12 (AC 9) | |
| 0.3 | Fresh venv: `python3 -m venv .venv-val && source .venv-val/bin/activate && pip install -r requirements-dev.txt` works | |
| 0.4 | `pytest` passes offline in < 30 s (AC 7); note the time and coverage % | time: ___ s · coverage: ___ % |
| 0.5 | Every FR in the traceability table of `tasks.md` has its tests present (AC 8) | |
| 0.6 | `tests/test_sem_requests_direto.py` passes (no direct `requests` calls outside `http_sapl.py`) | |

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
| C | `val_c` | 1 outside AC/PR (see §1.3) + `sapl.cascavel.pr.leg.br` | `emenda impositiva` only | **yes** | PDFs, other SAPL versions, `fonte` | 10–30 min |
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
   fallback). Record it: `__________________`.
2. Put only `emenda impositiva` in the keywords file (keep a copy of the
   original).
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
print('ok rows with empty Titulo:', (ok.Titulo == '').sum())          # expect 0
print('erro rows without reason:', ((df.status == 'erro') & (df.erro == '')).sum())  # expect 0
print(df[df.status == 'erro'].erro.value_counts())
```

| Check | Expected | Result |
|---|---|---|
| `ok` rows with empty `Titulo` | 0 | |
| `erro` rows without a reason | 0 | |
| Share of `erro` rows | small; each with a reason that matches the log | ___ % |
| Rows vs. 2026-10-15 (1195 unique links) | similar order of magnitude; differences explained by new matters on the sites | ___ |

### 2.2 Rate limit respected — AC 2 (runs A and C)

Count requests per host in any 60-second window from the DEBUG lines of the
HTTP client. Line format:
`2026-10-24 10:00:00,123 DEBUG sapl_scrap.http <host> | <url> | <status ou erro> | tentativa <n> | espera <s>`

```python
import re, collections, datetime as dt
linhas = open('val_a_proj/val_a.log', encoding='utf-8').read().splitlines()
pat = re.compile(r'^(\S+ \S+) DEBUG sapl_scrap\.http (\S+) \| \S+ \| (\S+) \| tentativa')
por_host = collections.defaultdict(list)
status = collections.Counter()
for l in linhas:
    m = pat.match(l)
    if m:
        t = dt.datetime.strptime(m.group(1)[:19], '%Y-%m-%d %H:%M:%S')
        por_host[m.group(2)].append(t)
        status[m.group(3)] += 1
print(status)                                     # 429 count, timeouts...
for host, ts in por_host.items():
    ts.sort(); i = 0; pico = 0
    for j, t in enumerate(ts):
        while (t - ts[i]).total_seconds() >= 60: i += 1
        pico = max(pico, j - i + 1)
    print(f'{host:40s} {len(ts):6d} requests  max/60s = {pico}')   # expect ≤ 35
```

| Check | Expected | Result |
|---|---|---|
| Max requests per host per 60 s (A) | ≤ 35 for every host | |
| Max requests per host per 60 s (C, with PDFs) | ≤ 35 for every host | |
| Number of `HTTP 429` lines in the logs | 0, or few and each followed by a wait ≥ `Retry-After` | |

### 2.3 Fields filled — AC 3 and FR-10a (runs A and C)

```python
for c in ['Data', 'Ementa', 'Tipo de Materia Legislativa', 'texto_original',
          'Regime Tramitacao', 'Em Tramitacao', 'Ultima Atualizacao']:
    print(f'{c:30s} filled in {(ok[c] != "").mean():.0%} of ok rows')
print(df.fonte.value_counts())
```

| Check | Expected | Result |
|---|---|---|
| `Data` filled | ≈ 100 % of `ok` rows (every page inspected had a date) | |
| `texto_original` filled for Rio Branco | clearly higher than in the 2026-10-15 run (bug fix) | |
| `Assuntos`, `texto_integral` columns | absent | |
| `Materia Anexada`, `Regime Tramitacao`, `Ultima Atualizacao` (api rows) | filled where the site has them | |
| `fonte` | `api` for the Acre houses; record any `html` house | |
| Spot check: open 5 random `ok` rows in the browser and compare Título, Ementa, Data, Tipo, PDF link | all match | |
| No `ip` / `user` columns or values in the output | none | |

### 2.4 No duplicates — AC 4 (run A)

```python
print('duplicate keys:', df.duplicated(['Link Casa', 'sapl_id']).sum())   # expect 0
print('rows with >1 keyword:', df.Palavras.str.contains('; ').sum())
```

| Check | Expected | Result |
|---|---|---|
| Duplicate house + `sapl_id` | 0 | |
| Rows found by more than one keyword | > 0 (≈ 111 duplicates in the old test), `Palavras` lists all | |

### 2.5 Interrupt and resume — AC 5 (run B vs A)

```python
a = pd.read_csv('val_a_proj/val_a_resultado_final.csv', dtype=str).fillna('')
b = pd.read_csv('val_b_proj/val_b_resultado_final.csv', dtype=str).fillna('')
k = ['Link Casa', 'sapl_id']
print('same keys:', set(map(tuple, a[k].values)) == set(map(tuple, b[k].values)))
cols = [c for c in a.columns if c not in ('raspada_em', 'Ultima Atualizacao', 'status', 'erro')]
m = a.merge(b, on=k, suffixes=('_a', '_b'))
dif = {c: (m[c + '_a'] != m[c + '_b']).sum() for c in cols if c not in k}
print({c: n for c, n in dif.items() if n})   # expect {} or differences explained by site edits
```

Then in `val_b_proj/val_b.log`, check that no matter recorded `ok` before
the interruption was requested again after the resume.

| Check | Expected | Result |
|---|---|---|
| Resume offered for existing `val_b` | yes, no crash | |
| Search not redone after resume (searches were `completa`) | no search URLs in the log after the resume point | |
| Matters `ok` before Ctrl+C not requested again | 0 repeats | |
| Same set of keys as run A | yes | |
| Field differences A vs B | none, or each explained by a site edit between the runs (check `Ultima Atualizacao`) | |
| Summary after resume counts the whole project | yes | |

### 2.6 Downloads (run C)

```python
import os
c = pd.read_csv('val_c_proj/val_c_resultado_final.csv', dtype=str).fillna('')
print(c.download_status.value_counts())
pasta = 'val_c_proj/downloads'
arqs = os.listdir(pasta)
print(len(arqs), 'files |', [a for a in arqs if a.endswith('.part')], '<- .part (expect none)')
faltando = [a for a in c[c.download_status == 'ok'].arquivo_pdf if a not in arqs]
print('ok without file:', faltando)                                   # expect []
print('empty files:', [a for a in arqs if os.path.getsize(os.path.join(pasta, a)) == 0])  # expect []
```

| Check | Expected | Result |
|---|---|---|
| File names `<host>_<sapl_id>.pdf` | yes | |
| `.part` files left | none | |
| `ok` rows have their file; no empty files | yes | |
| `sem_pdf` rows have empty `texto_original` | yes | |
| 3 random PDFs open and match the matter | yes | |
| Rate limit with downloads (§2.2 on `val_c.log`) | ≤ 35 per host per 60 s | |

### 2.7 Other SAPL versions (run C)

| Check | Expected | Result |
|---|---|---|
| House outside AC/PR: `fonte` | record `api` or `html` | |
| If `html`: fields filled as in §2.3 | yes, or missing fields listed here as new tasks | |
| Unknown page structure leads to empty fields, not crashes | yes | |

### 2.8 Update mode — Q5 (run D)

| Check | Expected | Result |
|---|---|---|
| Files `val_c_resultado_final_ATUALIZADO_<data>.csv` and `val_c_estado_ATUALIZADO_<data>.csv` created | yes | |
| Same keys as C's final CSV; status columns filled | yes | |
| `downloads<data>/` created without crash, even if it already exists (run D twice) | yes | |

### 2.9 Authors and procedure script (run E)

| Check | Expected | Result |
|---|---|---|
| Script lists the CSVs and asks which one | yes | |
| Input file unchanged; new `<entrada>_autoria_tramitacao.csv` written | yes | |
| `Autoria` and `Tramite` filled; `Tramite` is text (`data \| local \| destino \| status`) | yes | |
| Failures in `status_autoria` / `status_tramitacao` / `erro_autoria_tramitacao` | yes | |
| Rate limit respected (§2.2 on `autoria_e_tramitacao/autoria_tramitacao.log`) | ≤ 35 per host per 60 s | |

### 2.10 Prompts and project handling — AC 6

| Check | Expected | Result |
|---|---|---|
| Each prompt: type `x`, empty, `9` → asked again, no crash | yes, for every prompt | |
| Limit menu rejects `5` | yes | |
| "50 últimas casas" selects 50 (new project with reuse `1`, limit `3`, then Ctrl+C after the first search; `wc -l <proj>/casas_resultado.csv` = 51) | 50 | |
| Sul/Sudeste `1` with reused table → only RJ, SP, RS, SC, MG, ES, PR houses searched | yes | |
| New project with existing name → resume / other name, never overwritten | yes | |
| Ctrl+C at a prompt exits cleanly (no traceback flood) | yes | |

### 2.11 Summary and log — FR-25, FR-26

| Check | Expected | Result |
|---|---|---|
| Summary printed at the end of A, B, C, D | yes | |
| Summary counts match the CSV (§2.1 counts) | yes | |
| With failures: summary says to resume the project to retry | yes | |
| `<nome>.log` exists with INFO and per-request DEBUG lines | yes | |

## 3. Result

| Acceptance criterion (spec §8) | Section | Result |
|---|---|---|
| 1. No silent empty rows | 2.1 | |
| 2. ≤ 35 requests/min per site | 2.2 | |
| 3. `Data` filled | 2.3 | |
| 4. No duplicates, all keywords | 2.4 | |
| 5. Resume equals uninterrupted run | 2.5 | |
| 6. Prompts robust, no overwrite | 2.10 | |
| 7. `pytest` offline < 30 s | 0.4 | |
| 8. Traceability complete | 0.5 | |
| 9. CI green on 3.10 and 3.12 | 0.2 | |

**Issues found** (each becomes a task in `tasks.md`):

| # | Description | Task | Fixed and re-checked |
|---|---|---|---|
| | | | |

**Decision:** ☐ merge into `main` ☐ fix and re-run

**Notes** (run times, number of matters, anything unexpected):
