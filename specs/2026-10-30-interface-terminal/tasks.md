# Tasks: Terminal interface review (questions, menus, progress)

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md) · **Status:** Approved 2026-10-30
- **Branch:** `spec/2026-10-30-interface-terminal` (from `main`)

Rules for every task (same as earlier specs):
- A task is done when its tests are written, `pytest` passes offline, `ruff`
  passes and CI is green on the branch.
- One commit per task, at most. Message in Portuguese, starting with the task
  id. No AI co-author trailers. Check pytest's own exit code before
  committing.
- Tick the box here in the same commit.

## Phase A: Foundations

- [x] **T01 Dependencies and prompts** (FR-1, FR-2, NFR-1; plan §4)
  - `questionary>=2.0` and `rich>=13.7` in `pyproject.toml`;
    `tech-stack.md` (Interface row, dependencies).
  - `sapyl/interface/perguntas.py`: `Opcao`, `Perguntas`, `PerguntasTexto`,
    `PerguntasMenu` (`unsafe_ask`, injectable `input`/`output`),
    `criar_perguntas` (TTY check, injected reader, `SAPYL_MENUS=0`).
  - `test_camadas.py`: nothing outside `interface` imports `rich`,
    `questionary` or `prompt_toolkit`.
  - Tests: `test_perguntas.py` (texto forms, menus through pipe input,
    Ctrl+C, mode choice).
- [x] **T02 Keywords, spreadsheet and states** (FR-7, FR-10, FR-12, FR-13; plan §6.3)
  - `palavras.ler_palavras` raising `EntradaInvalida` (no file, no column,
    empty); `palavras.descrever` (query → plain words).
  - `casas`: spreadsheet check with `EntradaInvalida`, `ufs_da_planilha`,
    `filtrar_estados`; old `sul_sudeste` and `limite` `'2'`/`'3'` still work.
  - Tests: `test_palavras.py`, `test_casas.py`.
- [x] **T03 Project status and lazy creation** (FR-4a, FR-15; plan §6.2)
  - `projeto.Situacao`, `projeto.situacao(projeto)` (read-only); project
    folder created only by an explicit call.
  - Tests: `test_projeto.py` (each status, old project, state file untouched).

## Phase B: Flows

- [x] **T04 Main menu, lists, help and new project** (FR-3 to FR-16; plan §6.1–6.4)
  - New menu loop, `ajuda.py`, project lists with status, update and authors
    choosers (with `Outro arquivo CSV…`).
  - New-project flow: keywords first, name, house list, states, how many,
    PDFs, confirmation (Começar / Mudar respostas / Cancelar); `config.json`
    with `estados`; `preparar_casas` with `filtrar_estados`.
  - `ler_paralelo` before any message; short confirmations for resume,
    update and authors.
  - Tests: every flow scripted in texto mode; `respostas_novo_projeto` helper
    in `tests/apoio.py`; existing scripts migrated; early checks; cancel
    leaves nothing; old config resumes with the same houses.

## Phase C: Progress and end of run

- [x] **T05 Quiet terminal** (FR-19; plan §5.1, §5.3)
  - `registro.andamento`; per-item lines in `busca`, `materias`,
    `downloads`, `autoria`, `casas` become DEBUG progress records;
    `execucao.por_casa` start/finish lines and tagged progress line;
    `registro.configurar(..., terminal=None)`.
  - Tests: per-item lines only in the file; start/finish lines in the
    terminal; log file content unchanged otherwise.
- [x] **T06 Status model and texto-mode line** (FR-18 model, FR-20; plan §5.2)
  - `interface/status.py`: `Andamento`, `HandlerAndamento`, time-left
    estimate, `linha()`; counters from the state callback.
  - Tests: `test_status.py` (records, threads, fake-clock estimate).
- [x] **T07 Live panel** (FR-18, FR-21 panel; plan §5.3)
  - `PainelAoVivo` with `rich.live`; rich terminal handler on the same
    console; stopped on Ctrl+C; summary panel in menus mode.
  - Tests: recording console render; panel stopped after an interruption.
- [x] **T08 Next steps, authors offer, messages and errors** (FR-17, FR-21, FR-21a, FR-22; plan §6.5, §6.6)
  - `Fim` result; "Próximos passos" in both summaries; FR-21a offer;
    interrupted messages with the menu path; error table in `main`
    (including `sapyl_erro_<data>.log` before a log exists).
  - Tests: summaries with/without failures; offer yes/no/not asked;
    each row of the error table.

## Phase C2: Amendment after the first use (spec FR-23, FR-24)

- [ ] **T11 Voltar** (FR-23; plan §10a)
  - `Voltar` in `perguntas.py` (both modes); step loop in the new-project,
    resume, update and authors flows; confirmation `Começar / ← Voltar /
    Cancelar`.
  - Tests: back and forth through every step; Voltar from the first step;
    texto `<`; menus via pipe input.
- [ ] **T12 Organised run output** (FR-24; plan §10a)
  - Header and stage lines; "Começando" to the log; `✓ <host>: …`; panel in
    sections; two-line texto block; structured counters.
  - Tests: recording console render of every section; texto block; terminal
    lines of a full run.
- [ ] **T12b Docs** for T11–T12 (README, page).

## Phase D: Docs and validation

- [x] **T09 Documentation and version**
  - README ("Como usar", "Retomar um projeto", "Resumo e log",
    `SAPYL_MENUS=0`), project page, version 0.4.0.
  - Tests: `test_site.py` / `test_instalacao.py` still pass.
- [ ] **T10 Validation** (spec §8)
  - `validation.md`: real 10-house run in one state in an interactive
    terminal, checked by the user (menus, confirmation, live status, Ctrl+C,
    resume from the list, summary, authors offer); a piped-input run; Windows
    if possible; time to draw the project list on the largest local project.
