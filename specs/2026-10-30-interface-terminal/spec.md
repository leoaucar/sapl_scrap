# Spec: Terminal interface review (questions, menus, progress)

- **Status:** Approved 2026-10-30
- **Date:** 2026-10-30
- **Covers:** ROADMAP Phase 2b (Melhorar a usabilidade), first part: the
  terminal interface. The workflow changes found in the same review are
  ROADMAP Phase 2c, a later spec (§9).
- **Depends on:** [2026-10-27-paralelismo](../2026-10-27-paralelismo/spec.md),
  merged into `main` (version 0.3.0)
- **Principles:** [constitution](../constitution.md) · **Stack:** [tech-stack](../tech-stack.md)

## 1. Problem

The program works, but using it from the terminal is harder than it needs to
be for a researcher. A review of the current flow (code reading plus a run
from a fresh folder, 2026-10-30) found:

**Questions and menus**

- F1. Every answer is a typed number, including yes/no (`1- sim, 2- não`).
  Typos are asked again, but nothing can be picked with the arrow keys.
- F2. The first menu mixes "new" and "resume" in one option (`1- novo projeto
  ou retomar um projeto`); resuming means typing the exact name of an existing
  project, and the existing projects are not listed (they are listed only in
  options 2 and 3). There is no way to leave the menu other than Ctrl+C.
- F3. House selection is two unrelated questions: "restrict to Sul and
  Sudeste?" and "limit the search for a test?", whose option `1` means *no*
  limit. There is no way to pick other states. "50 first" and "50 last"
  houses follow the spreadsheet order, which means nothing to a user.
- F4. "Use the same house table as the last project?" does not say what the
  alternative costs (testing every site again, up to ~15 min) or how old the
  table is.
- F5. The download question does not mention size (about 10 MB per PDF; a
  full run can pass 100 GB).

**Keywords and early failures**

- F6. Keywords are read from `arquivos_csv/palavras_chave.(csv|xlsx)` only
  after every question is answered, and are never shown in plain words. The
  only echo is `Buscando os termos: "plano+diretor", …` in SAPL query syntax,
  after the run has started.
- F7. If the keyword file is missing (e.g. `sapyl` run from any folder other
  than the repository root), the program asks every question, then crashes
  with a Python traceback (`FileNotFoundError`) and leaves an empty
  `<nome>_proj/` folder behind. A wrong column name or an empty file fails the
  same way.
- F8. "Buscando os termos" is printed before an invalid `paralelo` value is
  reported, so the run seems to start and then stops.
- F9. Nothing is shown before the run starts: how many houses, how many
  searches, whether PDFs will be downloaded. There is no last chance to
  cancel.

**Progress and end of run**

- F10. During a run the terminal prints one line per matter and per PDF from
  up to 8 houses at once: thousands of interleaved lines. The overall progress
  line appears only once a minute and has no time estimate.
- F11. The summary is plain text; the result path is there, but nothing says
  what to do next (open the CSV, resume after failures) in the terms of the
  menu.
- F12. The Ctrl+C message says to "choose 1 / retomar"; it must match the
  menu after this spec.
- F13. There is no way to see how a project stands (done, interrupted, with
  failures) without running it, and no help inside the program: keyword
  syntax and where the files are only appear in the README.
- F14. Authors/procedure is a separate option the user has to remember to run
  after the project, typing the project name again.

## 2. Goals

1. Every choice is picked from a menu with the arrow keys (or typed, when the
   terminal is not interactive). Free text is asked only for the project name
   and for file paths.
2. The new-project questions are few, in a logical order, and say what each
   answer costs.
3. The keywords are read and shown in plain words before any project folder
   is created; missing or invalid input files give a clear message, never a
   traceback, and leave nothing behind.
4. Before a run starts, a confirmation screen sums up what will happen; the
   user can start, change the answers or cancel.
5. During a run, the terminal shows a live status: overall progress bar,
   houses in progress, counters and an estimated time left. Detailed lines go
   to the log file only.
6. The summary at the end says where the result is and what to do next,
   and offers authors/procedure for the result just produced.
7. The project list shows how each project stands, and a short help screen
   is available from the main menu.
8. Everything keeps working without an interactive terminal (piped input,
   tests, logs captured by a script), with the same questions as numbered
   prompts.

## 3. Non-goals

- Command-line options and a configuration file (`argparse`, `config.yaml`):
  ROADMAP Phase 7. `sapyl` keeps only `--version`.
- Changes to the project folder layout, the output files, the update and
  authors/procedure workflows, or resuming a search from its last page:
  ROADMAP Phase 2c (§9).
- Typing keywords in the terminal (the file stays the only source) and keyword
  suggestions (Phase 3b).
- A web or full-screen (TUI) interface: Phase 4.
- Any change to scraping, limits, the state file or the final table.

## 4. Users and scenarios

- **S1. First run.** A researcher runs `sapyl`, picks "Novo projeto", types a
  name, checks two states in a list, picks "teste com 10 casas", says no to
  PDFs, sees the keywords and a summary ("10 casas, 3 palavras, 30 buscas, sem
  PDFs"), confirms, and watches a progress bar until the summary.
- **S2. Missing keyword file.** The researcher runs `sapyl` in another folder.
  Before any question about the project, the program says it did not find
  `arquivos_csv/palavras_chave.csv` or `.xlsx` in that folder, explains the
  expected format (column `Palavras`) and points to the example files. No
  folder is created; exit code 2.
- **S3. Resume.** The researcher picks "Retomar um projeto" and chooses the
  project from a list; the run continues without questions.
- **S4. Change of mind.** On the confirmation screen the researcher picks
  "Mudar respostas", answers again, and confirms.
- **S5. Scripted / piped run.** Input comes from a pipe (or a test). The same
  questions appear as numbered prompts, answered with numbers or `s`/`n`;
  progress is printed as plain lines, like today.

## 5. Functional requirements

### 5.1 Prompts

- **FR-1** Two prompt modes with the same questions and the same answers:
  - *menus* (interactive terminal: stdin and stdout are TTYs): arrow-key
    select lists, a checkbox list for the states, yes/no as a select list
    (`Sim` / `Não`), text input for names and paths;
  - *texto* (anything else, or when a reader function is injected, as in the
    tests): numbered options; yes/no accepts `s`, `n`, `sim`, `não`/`nao`,
    `1`, `2` (case and spaces ignored); invalid answers are asked again, as
    today.
- **FR-2** Ctrl+C in any prompt (both modes) and Ctrl+D / end of input in
  *texto* mode stop the program with the interrupted message (FR-17) and exit
  code 1, as today. A prompt library that returns "no answer" on Ctrl+C must
  not be read as a valid answer.

### 5.2 Main menu

- **FR-3** First menu: `Novo projeto`, `Retomar um projeto`, `Atualizar um
  projeto`, `Autoria e tramitação`, `Ajuda`, `Sair`. `Sair` exits with code 0
  and no further output.
- **FR-4** `Retomar um projeto` lists the existing projects (`*_proj/` in the
  working folder) to pick from, each with its status (FR-4a). With no
  projects, it says so and returns to the menu. Typing a name that already
  exists under `Novo projeto` still offers to resume it (today's behaviour).
- **FR-4a** Project status, read from the project files only (no request):
  one of `concluído`, `concluído com falhas` (matters, searches or PDFs with
  `erro`/`incompleta` in the state file), `interrompido` (state file without a
  final result, or older than the last log), `não iniciado` (no state file);
  plus the date of the last run (newest log) and the number of matters in the
  final result. Old projects without `logs/` or `config.json` show what can be
  read and `?` for the rest. Shown in the lists of FR-4 and FR-5, and in the
  confirmation of FR-16.
- **FR-4b** `Ajuda` shows one screen, then returns to the menu: what each
  menu option does; the keyword file (where it is looked for in the working
  folder, the `Palavras` column, the space/comma syntax, the example files);
  where the results are (`<nome>_proj/<nome>_resultado_final.csv`); how to
  resume; the README and project page links.
- **FR-5** `Atualizar um projeto` lists only projects with a final result.
  `Autoria e tramitação` lists projects with a final result plus an option
  `Outro arquivo CSV…` that asks for a path (today's validation kept).

### 5.3 New project

Order of the questions (after the keywords are read and shown, FR-12 and FR-13):

- **FR-6** **Houses list**: shown only if `arquivos_csv/casas_resultado.csv`
  exists. Options: `Usar a lista já testada (de <dd/mm/aaaa>, <n> casas no
  ar)` and `Testar os sites de novo (pode levar até ~15 min)`.
- **FR-7** **States**: checkbox list of the UFs present in the house
  spreadsheet, with two shortcuts at the top: `Todos os estados` and `Sul e
  Sudeste`. Nothing checked means all states. In *texto* mode: type UFs
  separated by commas or spaces (`SP, RJ`), Enter for all, or `sul-sudeste`;
  unknown UFs are named and asked again.
- **FR-8** **How many houses**: `Todas as casas dos estados escolhidos (<n>)`
  and `Teste com 10 casas (bom para conferir as palavras)`. The options "50
  primeiras" and "50 últimas" are removed from the menu.
- **FR-9** **PDFs**: yes/no, with the note "cerca de 10 MB por matéria; uma
  execução completa pode passar de 100 GB".
- **FR-10** Saved in `config.json`: `estados` (list of UFs, empty = all) and
  `limite` (`'1'` all, `'4'` 10 houses), alongside today's keys.
  Projects created before this spec (with `sul_sudeste` and `limite` `'1'`
  to `'4'`) resume exactly as before; the old keys keep their meaning.
- **FR-11** The global house table (`arquivos_csv/casas_resultado.csv`) is
  replaced only when every house was tested (all states, all houses), as
  today.

### 5.4 Keywords and early checks

- **FR-12** For a new project, the keyword file is read **before** the
  project name is asked. Missing file, missing `Palavras` column, or no
  keyword at all → a message saying which file was looked for, in which
  folder, the expected format, and the example files; exit code 2; nothing
  created. The same check covers `arquivos_csv/casas_legislativas.xlsx`.
- **FR-13** The keywords are shown in plain words, one per line, numbered,
  with terms searched together joined by ` + ` (e.g. `2. orçamento + emenda
  impositiva (juntos na mesma matéria)`), never in SAPL query syntax.
- **FR-14** `paralelo` from `config.json` (resume, update, authors) is
  checked before anything is printed about the run (fixes F8). Invalid value
  → today's message and exit code 2.

### 5.5 Confirmation

- **FR-15** Before a new project starts, a summary: project name and folder,
  states, number of houses (or "a testar"), keywords (FR-13), number of
  searches (houses × keywords, or "até" when the houses will be tested),
  PDFs yes/no, houses at once. Options: `Começar`, `Mudar respostas` (asks
  FR-6 to FR-9 again, keeping the name), `Cancelar` (exit code 0; the empty
  project folder is removed). The answers are saved to `config.json` only
  after `Começar`.
- **FR-16** Resume, update and authors show a short version (project, what
  is left to do when known, PDFs) and ask `Continuar` / `Cancelar`.

### 5.6 Progress, messages and summary

- **FR-17** Interrupted message (Ctrl+C or an unexpected failure in a house)
  names the menu path: for a project, `rode sapyl, escolha "Retomar um
  projeto" e depois "<nome>"`; for authors/procedure, the same entry.
- **FR-18** During a run in *menus* mode, a live status at the bottom of the
  terminal, refreshed at least every second:
  - an overall bar of houses done / total, elapsed time and an estimated time
    left (shown once at least one house is done and 1 minute has passed;
    otherwise "calculando");
  - counters: searches done, matters scraped / with error, PDFs downloaded /
    with error (when enabled);
  - one line per house in progress: host and current stage with its count
    (`buscando 2/3`, `matérias 45/120`, `PDFs 3/40`, `testando`).
- **FR-19** In the terminal, above the status: one line when a house starts
  and one when it finishes (with its counts), warnings and errors. The
  per-matter, per-page and per-PDF lines go to the log file only (DEBUG). The
  log file keeps everything it has today.
- **FR-20** In *texto* mode there is no live status; the terminal gets the
  lines of FR-19 plus the progress line every minute, now with the estimated
  time left.
- **FR-21** The summary keeps today's content and adds a "Próximos passos"
  part: open `<resultado>` in a spreadsheet; if there were failures, resume
  with the menu path of FR-17; the log path. In *menus* mode it is shown in a
  framed panel; the same text goes to the log.
- **FR-21a** After the summary of a new, resumed or update run that produced
  a final result, ask (yes/no, default no) whether to fetch authors and
  procedure for that result now. Yes → the authors/procedure flow runs on that
  exact file (no second name prompt), with its own summary and log, as if
  chosen from the menu. The question says it makes about 2 requests per matter
  and gives the matter count. Not asked when the run was interrupted or
  produced no matter.
- **FR-22** Expected errors (missing or unreadable input files, permission
  denied, disk full, invalid `config.json`) end with a one-paragraph message
  and exit code 2, no traceback. Unexpected errors end with a short message
  pointing to the log, where the traceback is written; exit code 1.

### 5.7 Amendment after the first use (2026-10-30)

Asked by the user after running the branch, decided with them the same day.

- **FR-23 Voltar (one step back).** Every question in a flow can go back one
  step, keeping the answers already given:
  - new project: name → (house list) → states → how many → PDFs →
    confirmation. *Voltar* on the name returns to the main menu. The
    confirmation becomes `Começar` / `← Voltar` (back to the PDFs question) /
    `Cancelar`; *Voltar* replaces *Mudar respostas*.
  - resume, update and authors: the questions and the confirmation
    (`Continuar` / `← Voltar` / `Cancelar`) go back to the previous question,
    then to the project list, then to the main menu.
  - *menus* mode: `← Voltar` as the last option of every list, as the first
    item of the states checkbox, and an empty answer in the name field
    (said in the hint). *texto* mode: the numbered `← Voltar` option, and
    `<` in the yes/no, states and name questions.
- **FR-24 Organised run output.** After `Começar`/`Continuar`:
  - a header block, with blank lines around it: project, states, houses,
    keywords; then one line per stage (`Etapa 1 de 2: testando os sites (10
    casas)`, its result, `Etapa 2 de 2: busca e raspagem (…)`); the long
    "Buscando os termos" line goes to the log only (the keywords were shown
    in the confirmation);
  - above the panel only finished houses (`✓ <host>: 23 buscas, 12 matérias
    (1 com erro)`), warnings and errors; the "Começando" lines go to the log;
  - the live panel (*menus* mode) in sections, as chosen by the user: a
    header line (project · states · houses · keywords) and a rule; `Casas`
    bar with `4 de 10 (40%)`; `Tempo` with elapsed and time left; a blank
    line; `Buscas` (`92 de 230 completas`), `Matérias`, `PDFs` (`não
    pedidos` when off); a blank line; `Em andamento (n)` with one row per
    house: host, stage, `feitos/total` and a small bar;
  - *texto* mode: the minute line becomes a two-line block (houses and time;
    then searches, matters, PDFs and time left).

- **FR-25 Project lists, newest first.** The lists of FR-4 and FR-5 are
  sorted by last update, most recent at the top, and each entry shows its
  creation date and last-update date: `nome — concluído · criado em
  28/10/2026 · atualizado em 30/10/2026 14:05 · 1.189 matérias`.
  - *created*: the earliest run log (`logs/<nome>_<data_hora>_<modo>.log`),
    else the first row of the state file, else `config.json`'s date;
  - *last update*: the newest modification among the project's files
    (results, state, matters, logs, config), so update and authors runs
    count too;
  - unknown dates show `?`. Read-only, no request (as FR-4a).

## 6. Non-functional requirements

- **NFR-1** New dependencies: `questionary` (menus; MIT, with
  `prompt_toolkit`, BSD-3) and `rich` (live status and panels; MIT). Both
  AGPL-compatible, both support Python 3.10+ on Linux, macOS and Windows. The
  plan justifies them (constitution §5) and updates `tech-stack.md`.
- **NFR-2** All prompt and status code stays in the `interface` layer, or
  behind a small callback that lower layers already use (`progresso`), so the
  layer check (`tests/test_camadas.py`) keeps passing without new upward
  imports.
- **NFR-3** Accents display correctly in UTF-8 terminals and in the Windows
  terminal; the log file stays UTF-8.
- **NFR-4** No change to request counts, limits, state or output files beyond
  the new `config.json` keys (FR-10).
- **NFR-5** User-facing text in Portuguese; identifiers in Portuguese.

## 7. Tests (offline)

- *texto* mode: scripted answers for every flow (new, resume from the list,
  update, authors with a project and with a CSV, `Ajuda`, `Sair`, `Cancelar`,
  `Mudar respostas`, authors offered after a run: yes and no), including
  invalid answers, `s`/`n`, UF typing and `sul-sudeste`.
- *menus* mode: the menu adapter driven by simulated key presses
  (`prompt_toolkit` pipe input, no real terminal), at least: a select, the
  states checkbox with a shortcut, yes/no, and Ctrl+C → interrupted.
- Early checks: missing keyword file, wrong column, empty list, missing house
  spreadsheet → exit code 2, message text, no project folder created.
- Old `config.json` (with `sul_sudeste`, `limite` `'2'`/`'3'`) resumes with the
  same houses as before.
- Status: the status model (counts, house stages, time-left estimate) tested
  without a terminal; the rendered panel checked with `rich`'s recording
  console; per-matter lines absent from the terminal handler and present in
  the log file.
- Summary: "Próximos passos" content with and without failures.
- Project status: one fixture project per status (concluded, with failures,
  interrupted, not started, old project without logs/config).
- Existing suites (layers, typing, no direct requests, network blocked) keep
  passing; CI on 3.10/pandas 2 and 3.12/pandas 3.

## 8. Acceptance

- All FRs covered by tests; `pytest`, `ruff check` and `ruff format --check`
  pass.
- Validation (`validation.md`): a real run on a small set of houses (one
  state, 10-house test) in an interactive terminal on Linux, checked by the
  user: menus, confirmation, live status, Ctrl+C and resume from the list,
  summary. A run with piped input shows the *texto* mode. If possible, the
  menus checked once in a Windows terminal (or noted as not checked).
- README ("Como usar", "Retomar um projeto", "Resumo e log") and the project
  page updated with the new questions; version 0.4.0.

## 9. Left for later (ROADMAP Phase 2c)

Found in the same review, out of scope here; listed in the ROADMAP as
"Fase 2c: Fluxo de trabalho e novas opções", right after this spec:

- Extend an existing project with new keywords or states, without scraping
  again what is already there.
- Count results only (searches without scraping), to test keywords cheaply.
- Download PDFs of an existing project later (all, or only the `Relevante`
  ones) without re-scraping, which today needs update mode.
- Re-test the house list on its own, outside a new project.
- Output that Excel opens correctly (today: UTF-8 CSV without BOM and with
  commas; Excel in Portuguese shows broken accents and one column). An
  `.xlsx` copy, or a CSV Excel reads correctly.
- A settings menu for `paralelo` instead of editing `config.json`.
- Project folder layout: the final result sits among the internal files
  (house table, search pages, links, matters, state, cache, config, logs);
  move the internals to a subfolder, reading old projects as they are.
- Running `sapyl` from any folder: ship the house spreadsheet with the
  package and look for the keyword file in a known place (or copy it into the
  project at creation, so the project is self-contained).
- Resume a search from its last page instead of page 1.
- Update mode: one output per run with `_ATUALIZADO_<dd_mm_aaaa>` (date format
  differs from the logs, `aaaa-mm-dd`); several files pile up.
- Authors/procedure output location (next to the input) and its naming.
- Decide which of these go to Phase 7 instead.

## 10. Open questions

None at the moment. Decided with the user on 2026-10-30: keywords stay in the
file but are shown and confirmed; states as a checkbox list plus "how many";
quieter terminal with a live progress bar/status; arrow-key menus with
`questionary` + `rich`, falling back to numbered prompts; project status in
the lists, a help screen and authors/procedure offered after a run are in
this spec; the other workflow suggestions go to ROADMAP Phase 2c.
