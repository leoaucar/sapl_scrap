# Validation: Terminal interface review

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Tasks:** [tasks.md](tasks.md)
- **Branch:** `spec/2026-10-30-interface-terminal` · **Version:** 0.4.0
- **Status:** Passed (2026-10-30), except V5 (Windows, not checked; in the ROADMAP).
  Merged into `main` before the real-site checks at the user's request; the
  bugs they found were fixed on `main` the same day (§3). Server ceiling raised
  to 150 (§4).

## 1. Automated (offline)

| Check | Result |
|---|---|
| `pytest` (3.12, pandas 3) | 468 passed (2026-10-30, after T11–T13) |
| `ruff check`, `ruff format --check` | pass |
| Layers: nothing outside `interface/` imports `rich`, `questionary`, `prompt_toolkit` | pass (`test_camadas.py`) |
| CI on 3.10/pandas 2 and 3.12/pandas 3 | pending: branch not pushed yet |

## 2. Manual checks done by Claude (2026-10-30)

| # | Check | Result |
|---|---|---|
| M1 | Numbered mode with piped input, from a copy of `arquivos_csv/`: menu, keywords in plain words, name, states typed (`SP RJ`), test with 10, no PDFs, confirmation, **Cancelar** | OK: "Cancelado. Nada foi feito.", exit 0, no folder created |
| M2 | `sapyl` from a folder without `arquivos_csv/` (the F7 crash) | Fixed: message with the folder searched and the expected format, exit 2, no folder (covered by tests) |
| M3 | Menus mode in a pseudo-terminal (`pty`), arrow keys and space: main menu, name, states checkbox with the *Sul e Sudeste* shortcut, "Teste com 10 casas", PDFs *Não*, **Cancelar**; requests sent to a dead proxy | OK: shortcut expanded to ES, MG, PR, RJ, RS, SC, SP; 713 houses counted; nothing created. Found and fixed: questionary's English hints ("Use arrow keys…") replaced by Portuguese ones |
| M4 | Time to draw the project list: 11 local validation projects (largest state file 116 KB) | 0.05 s in total; statuses read correctly (*concluído*, *concluído com falhas* for the ramp projects with 429s/errors, *interrompido*, *não iniciado*) |

### Incident: unplanned real-site run (M3, first attempt)

In the first `pty` attempt the scripted keys were one question off (there was
no house-list question), so **Começar** was selected and a real run started:
10 houses (Acre, the first 10 of the spreadsheet), 16:02:06–16:03:10, then
stopped when the script was killed. 240 requests in total, at most 32 to a
single site in that minute (the limit is 35), **no 429**, no PDFs. The
project was in Claude's scratch folder, not in the repository. It does show
the menus mode running a real project end to end (searches started in 8
houses at once). The second attempt routed all requests to a dead proxy and
killed the program after a timeout.

## 3. Real-site validation (2026-10-30)

Run by Claude at the user's request, in a real terminal emulated with a
pseudo-terminal (`pty`, 110×40, the program sees a TTY and uses the arrow-key
menus). The driver waits for each question's text before pressing keys and
moves the cursor until `»` is on the wanted option, so nothing is chosen
blind. Working folder `val_v04/` (untracked) with `palavras_chave.csv` =
`plano diretor`; state RR, test with 10 houses (3 on line).

| # | Check | Result |
|---|---|---|
| V1 | New project in menus mode: keywords shown, name, states checkbox (RR marked with Space), "Teste com 10 casas", PDFs *Não*, confirmation, *Começar* | ✅ Stage lines, `✓` lines and the sectioned panel as designed (header, `Casas` bar `2 de 3 concluídas (67%)`, `Tempo`, `Buscas 3 de 3 completas`, `Matérias 5 raspadas · 0 com erro`, `PDFs não pedidos`, `Em andamento (1)` with `sapl.boavista.rr.leg.br matérias 5/35`) |
| V2 | Ctrl+C after 5 matters, then *Retomar um projeto* → list → *Continuar* | ✅ Stopped within a second, exit 1, message `…escolha "Retomar um projeto" e depois "v04".`; the list showed `v04 — interrompido · criado em … · atualizado em …`; the resume scraped the 30 left and the project became *concluído* (35 matters) |
| V3 | Authorship offer after the resume, answered *Sim* | ⚠️→✅ First run: all 35 authorships done, then the program **froze** before writing the output (all 14 threads waiting on locks; ptrace blocked, no stack). Not reproduced in two replays nor in a 30-round offline stress test. Fixed by drawing the panel in its own thread, outside `rich`'s locks (our locks were taken inside `rich`'s refresh), plus `kill -USR1 <pid>` now prints every thread's stack. Replay with the fix: authorship done, output written, `USR1` printout worked mid-run |
| V4 | Numbered mode: `printf '6' \| sapyl`; `SAPYL_MENUS=0` with `<` to go back | ✅ |
| V5 | Windows terminal | ⏭️ Not checked (no Windows machine available) |
| V6 | CI on the branch and on `main` | ✅ `testes` and `pagina` green |
| V7 | ← Voltar in menus mode: from the states list to the name, empty name to the main menu, from the confirmation to the PDF question | ✅ |
| V8 | Install following the README (Linux) | ✅ with a finding: without `python3-venv`, `python3 -m venv` fails **and leaves a half-made `.venv`** that blocks the next try; README now says to delete it. (Checked with the ZIP download, later removed from the docs at the user's request; the steps after downloading are the same.) |

### Issues found during the validation, all fixed on `main`

1. **Freeze after the authorship offer** (V3): see the table.
2. **State list: Enter without Space meant "all states"** (found by the user:
   RJ under the cursor + Enter → a test with 10 Acre houses). Enter with
   nothing marked is now refused with a message (spec FR-7 amended).
3. **Time-left estimate too pessimistic** (V2: "faltam ~30 min" for 30
   matters on one site at 35/min): the rate counted the search time before
   the first matter; it now starts at the first matter.
4. **Half-made `.venv`** (V8): README note.

## 4. Server ceiling: 150 per minute (2026-10-30)

Asked by the user after the 29/10 ramp (`specs/2026-10-27-paralelismo/validation.md`
§7 kept 120 because 175 raised p95 1.55×). Same inputs as that ramp: the first
50 houses (`limite` `'2'`, still read from `config.json`), the 23 education
keywords, no PDFs, 8 houses at once; a fresh 120 baseline and then 150, 5
minutes apart, one program at a time. Measures with the same script for both.

Tool: `ferramentas/medir_rampa.py <pasta> <teto>` (on the 29/10 projects it
gives 120 max / 18 min at the ceiling / 20 min 30 s / p95 0.35 s for
`ramp_120`, matching the recorded values; it reports p95 0.48 s for
`ramp_175`, recorded as 0.51 s with the earlier script).

| Check | `ramp_120b` (17:59) | `ramp_150` (18:24) |
|---|---|---|
| Max requests per server per 60 s (`201.54.51.178`, 40 houses) | 120 | 150 |
| Minutes at the ceiling (≥ 95 %) | 18 (17:59–18:16) | 14 (18:24–18:37) |
| `HTTP 429` (hosts) / slow-downs | 0 / 0 | 0 / 0 |
| Response time median / p95, whole run (s) | 0.08 / 0.51 | 0.07 / 0.44 |
| Worst per-minute p95 on the shared server, at the ceiling | 0.75 s | 0.78 s |
| Timeouts / 5xx | 0 / 0 | 0 / 0 |
| Whole run | 19 min 38 s | 17 min 29 s (11 % faster) |
| Results | 416 matters `ok`, 966 searches, 0 incomplete | same 416 keys, same order, same statuses |

The server was slower than on 29/10 (p95 0.51 s at 120, against 0.35 s), which
is why the baseline was run again. The worst per-minute p95 of the 150 run
(1.23 s at 18:40) was on another provider's server (the state assembly of AM,
`159.60.67.5`), when only that house was left: not load on the shared server.

| Decision | Why (numbers) |
|---|---|
| **Raise the default to 150** (`padroes.LIMITE_POR_SERVIDOR`) | The ceiling of 150 was held for 14 minutes with 0 × 429, no slow-down, no timeouts/5xx; median and p95 were not higher than the same-day 120 run (0.07/0.44 s against 0.08/0.51 s; per-minute p95 at the ceiling 0.78 s against 0.75 s), well inside the 1.5× rule; same results; 11 % faster. README, page, ROADMAP and tech-stack updated. Projects created before keep the value in their `config.json` (120); edit it to use 150. |

