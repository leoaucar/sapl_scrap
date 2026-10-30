# Validation: Terminal interface review

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Tasks:** [tasks.md](tasks.md)
- **Branch:** `spec/2026-10-30-interface-terminal` · **Version:** 0.4.0
- **Status:** In progress (offline checks done; real-site checks with the user pending)

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

## 3. Pending: with the user (spec §8)

Run in a real terminal on Linux, in the repository folder:

- [ ] **V1 New project:** `sapyl` → Novo projeto → one state (e.g. AC) → teste
      com 10 casas → PDFs não → Começar. Check: menus, confirmation text, the
      live panel (bar, time left after the first minute, one row per house),
      only start/finish lines above it, summary in a frame with "Próximos
      passos", the authorship offer (answer *Não*).
- [ ] **V2 Ctrl+C and resume:** in a second run, Ctrl+C during the matters.
      Check: stops within seconds, message names "Retomar um projeto" and the
      project; the list shows it as *interrompido*; resuming finishes it.
- [ ] **V3 Authorship offer:** answer *Sim* once (small project). Check: runs
      on that result, its own summary.
- [ ] **V4 Numbered mode:** `SAPYL_MENUS=0 sapyl` and a piped run
      (`printf '6\n' | sapyl`).
- [ ] **V5 Windows terminal** (if available): menus, accents, panel. Otherwise
      noted as not checked.
- [ ] **V6 CI green** on the branch (needs a push).
- [ ] **V7 Amendment (FR-23 to FR-25):** `← Voltar` through every question of a
      new project (and `<` with `SAPYL_MENUS=0`); the run output in sections
      (header, stages, `✓` lines, sectioned panel); the project lists newest
      first with creation and update dates.
- [ ] **V8 Docs for beginners:** someone new follows the README install
      (ZIP download, venv, activation) on Windows or Linux without help.
