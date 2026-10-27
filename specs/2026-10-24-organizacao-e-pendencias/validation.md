# Validation: Code organization, SAPyL identity and leftover issues

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Tasks:** [tasks.md](tasks.md)
- **Status:** Not run
- **Run by / date:** _fill in_

Manual checks on the implementation branch after T01–T22, against real sites
where needed. They cover the acceptance criteria in spec §8. The branch is
merged only when every check is ✅, or each ❌ has become a task that was
fixed and re-checked. The GitHub rename (AC 9) is checked after the merge.

Runs must go **one at a time**: two processes would each have their own
rate limiter and could double the load on a site.

## 0. Preconditions

| # | Check | Result |
|---|---|---|
| 0.1 | Tasks T01–T22 ticked | |
| 0.2 | CI green: `testes` (3.10, 3.12, ruff + pytest) and `instalacao` | |
| 0.3 | `pytest` offline < 30 s; coverage ≥ 95 % (AC 2) | time: ___ s · coverage: ___ % |
| 0.4 | `ruff check` and `ruff format --check` clean (AC 2) | |
| 0.5 | Traceability table in `tasks.md` complete | |

## 1. Install and run — AC 1

In a new folder, with no previous virtual environment:

```bash
git clone <branch> sapyl-val && cd sapyl-val
python3 -m venv .venv && source .venv/bin/activate     # or: uv venv
pip install .
sapyl --version
python -m sapyl --version
python programa.py --version
sapyl            # menu appears; answer 3, then Ctrl+C → short message, no traceback
```

| Check | Expected | Result |
|---|---|---|
| `pip install .` works on a clean environment | yes | |
| The three `--version` calls print `0.2.0` | yes | |
| `sapyl` shows the 3-option menu, and Ctrl+C exits cleanly | yes | |

## 2. Repository contents — AC 3

```bash
git ls-files | grep -E 'casas_resultado\.csv|tabela_limpa|_proj/|\.log$|\.pdf$'
```

| Check | Expected | Result |
|---|---|---|
| Command output | empty | |
| Fresh clone: new project does not offer to reuse a house table | yes | |

## 3. Phase 1 project still works — AC 4

Use the Phase 1 validation project `val_a` as it is (back it up first with
`cp -r val_a_proj val_a_proj.bak`, since resuming and updating add files to it).

| Check | Expected | Result |
|---|---|---|
| Resume `val_a`: no search and no `ok` matter requested again (check the new log in `val_a_proj/logs/`) | 0 repeats | |
| Keywords warning appears if `palavras_chave.*` differs from `config.json` | yes | |
| Update `val_a`: `_ATUALIZADO_` files created, same keys | yes | |
| Old `val_a.log` untouched; new runs log to `logs/` | yes | |

## 4. New 10-house run — AC 7 and rate limit

Same inputs as Phase 1 run A (the 3 keywords, 10 Acre houses, no downloads),
project `val2_a`.

| Check | Expected | Result |
|---|---|---|
| `val2_a_paginas_busca.csv` size vs Phase 1 `val_a_resultados_crus_casas.csv` | ≥ 10× smaller | ___ MB vs ___ MB |
| Same set of keys as Phase 1 `val_a` (allowing for new matters on the sites) | yes, differences explained | |
| Max requests per host per 60 s (Phase 1 script, reading `logs/*.log`, using the `enviada` time) | ≤ 35 | |
| `cache.json` present; a resume of `val2_a` makes no API probe or name lookup already in it | yes | |

## 5. Authors and procedure — AC 5

Menu option 3 on project `val2_a`. Then, separately, on a CSV holding a few
matters from a house **without** API (if Phase 1 validation found one;
otherwise, record "not available").

| Check | Expected | Result |
|---|---|---|
| Uses the latest final of the project; input not modified | yes | |
| `fonte` = `api` for Acre houses | yes | |
| Ctrl+C halfway, then option 3 again on the same input: only the missing matters are requested | yes | |
| Output has the input columns + `Autoria`, `Tramite`, statuses | yes | |
| Spot check 5 matters in the browser: authors and latest procedure match | all match | |
| ≤ 35 requests per host per 60 s in the autoria log | yes | |
| HTML-only house: `fonte` = `html`, fields filled | yes / not available | |

## 6. Update with `Relevante` — AC 6

1. Back up `val2_a_proj/val2_a_resultado_final.csv`.
2. In that file, add a `Relevante` column (5 rows `sim`, one ` X `, the
   rest empty) and a `Notas` column with some text.
3. Run the update on `val2_a`.
4. Restore the backup afterwards.

| Check | Expected | Result |
|---|---|---|
| Update asks "só as relevantes?" | yes | |
| With `1`: only the 6 marked rows are re-scraped (log), and the output has 6 rows | yes | |
| `Relevante` and `Notas` columns kept, values intact, after the program columns | yes | |
| Without `Relevante` column: the question does not appear | yes | |

## 7. Broken houses — AC 8

Make a test house table (`arquivos_csv/casas_resultado.csv`, back up the
original) with:
- `https://sapl.marata.rs.leg.br/` (its name stopped resolving: on 2026-10-24
  it failed with `NameResolutionError`/`socket.gaierror`, yet the old shared
  table listed it as active). If it resolves again, use
  `https://sapl.naoexiste-sapyl.leg.br/` instead.
- one real Acre house

Run a new project with reuse `1` and limit `1`.

| Check | Expected | Result |
|---|---|---|
| Non-existent domain: 1 attempt only, reason `dns` (log) | yes | |
| The real house is searched normally | yes | |
| An SSL failure, if a known house has one: reason `ssl`, 1 attempt | yes / not available | |
| A redirecting house, if one is known: `url_final` recorded and used | yes / not seen | |

Restore the original house table afterwards.

## 8. Docs and identity

| Check | Expected | Result |
|---|---|---|
| README opens with "SAPyL — Raspador do Sistema de Apoio Legislativo" and the purpose | yes | |
| README install/use sections match what was run in §1 | yes | |
| `AUTHORS.md` citation uses SAPyL | yes | |
| `User-Agent` in the log/headers says `SAPyL/0.2.0` | yes | |
| `docs/index.html` opened locally: sections of FR-13a, readable at phone width and in dark mode | yes | |
| Site install/use steps say the same as the README | yes | |

## 9. After the merge: rename on GitHub — AC 9

Only with the user's go-ahead.

| Check | Expected | Result |
|---|---|---|
| `gh repo view leoaucar/sapyl` works | yes | |
| Old URL `github.com/leoaucar/sapl_scrap` redirects | yes | |
| `git remote -v` points to the new URL | yes | |
| README badge renders and links to the new Actions page | yes | |
| Clone URL in README works | yes | |
| Pages switched on (GitHub Actions), `pages` workflow green | yes | |
| `https://leoaucar.github.io/sapyl/` opens and matches `docs/` | yes | |
| Install steps from the site work in a fresh virtual environment | yes | |
| Repository homepage points to the site | yes | |

## 10. Result

| Acceptance criterion (spec §8) | Section | Result |
|---|---|---|
| 1. Install and command | 1 | |
| 2. Lint, format, tests, coverage | 0 | |
| 3. No generated/research data in git | 2 | |
| 4. Phase 1 project resumes and updates | 3 | |
| 5. Authors/procedure: API, HTML, resume, limit | 5 | |
| 6. Update keeps columns, filter works | 6 | |
| 7. Search file ≥ 10× smaller | 4 | |
| 8. DNS failure after one attempt | 7 | |
| 9. Repository renamed, links updated | 9 | |
| 10. Project site online, install steps work | 8, 9 | |

**Issues found** (each becomes a task in `tasks.md`):

| # | Description | Task | Fixed and re-checked |
|---|---|---|---|
| | | | |

**Decision:** ☐ merge into `main` ☐ fix and re-run

**Notes:**
