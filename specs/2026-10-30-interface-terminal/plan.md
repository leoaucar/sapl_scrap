# Plan: Terminal interface review (questions, menus, progress)

- **Spec:** [spec.md](spec.md) · **Status:** Approved 2026-10-30 · **Date:** 2026-10-30
- **Branch for implementation:** `spec/2026-10-30-interface-terminal`, from `main`
  (version 0.3.0)

## 1. Approach in one paragraph

First put every question behind one small interface with two implementations:
numbered prompts (today's behaviour, used by the tests and by piped input) and
arrow-key menus (`questionary`). Then rebuild the flows on it: main menu,
project lists with status, help, the new-project questions (keywords first,
states, how many houses, PDFs, confirmation), the short confirmations and the
offer of authors/procedure at the end. Separately, make the terminal quiet:
per-item lines become DEBUG and carry a small progress record; a status model
in the interface layer collects these records through a logging handler, and
`rich` draws it as a live panel (menus) or a line per minute (texto). Lower
layers keep logging as they do today and import nothing new. Errors get one
place in `main` that turns expected failures into messages and exit codes.

## 2. Findings used by this plan (2026-10-30)

| Topic | Finding | Consequence |
|---|---|---|
| Dependencies | `questionary` 2.1.1 (→ `prompt_toolkit` 3.0.53, `wcwidth`) and `rich` 15.0.0 (→ `markdown-it-py`, `mdurl`, `pygments`) resolve for Python 3.10 and 3.12; all MIT/BSD | `questionary>=2.0`, `rich>=13.7` in `dependencies` |
| `questionary` and Ctrl+C | `.ask()` catches Ctrl+C, prints "Cancelled" and returns `None`; `.unsafe_ask()` raises `KeyboardInterrupt` | Always `unsafe_ask()` (spec FR-2) |
| Testing menus | `prompt_toolkit` has `create_pipe_input()` and `DummyOutput`; questionary questions accept `input=`/`output=` | Menu adapter tests send key codes through a pipe, no terminal needed |
| Per-item lines | `materias.raspar_pendentes`, `downloads.baixar_da_casa`, `busca.buscar_casa`/`buscar`, `autoria.processar`, `casas.testar_casas` log one INFO line per matter, PDF, keyword, authors row or tested house | These become DEBUG with a progress record (§5.1); the log file keeps them |
| Progress line | `execucao.por_casa` logs the overall line every 60 s at INFO, built from the futures plus the `progresso()` text | Kept for the log and texto mode; tagged so the live panel's handler skips it |
| Terminal handler | `registro.configurar` always creates a `StreamHandler` | New optional argument to pass the terminal handler in (rich's, from the interface) |
| Project folder | `abrir_ou_criar` creates `<nome>_proj/` right after the name; `registro.configurar` needs the folder for the log | Folder and log are created only on `Começar` (fixes F7 and FR-15 cancel) |
| `Estado` | Opens the state file for appending on construction | Project status reads the file with `estado.ler_csv` only, never through `Estado` |
| Stored keywords | `config.json` keeps SAPL query syntax (`"orçamento"+"emenda+impositiva"`) | `palavras.descrever()` turns a query back into plain words, so old projects display well too |
| Old configs | `sul_sudeste` (bool) and `limite` `'1'`–`'4'` | `estados` derived from `sul_sudeste` when absent; `limitar_casas` keeps `'2'`/`'3'` |

## 3. Layout changes

```
sapyl/
  registro.py            andamento(...) helper; configurar(..., terminal=None);
                         tags for progress/house lines; resumo gains "Próximos passos"
  palavras.py            ler_palavras(pasta) with EntradaInvalida; descrever(consulta)
  casas.py               filtrar_estados(casas, ufs); ufs_da_planilha(); checks the
                         spreadsheet with EntradaInvalida; per-house test line → DEBUG
  busca.py, materias/, downloads.py, autoria.py
                         per-item lines → registro.andamento(...) (DEBUG)
  execucao.py            house start/finish lines; progress line tagged
  projeto.py             Situacao + situacao(projeto); created lazily (criar())
  interface/
    perguntas.py   NEW   Perguntas protocol, PerguntasTexto, PerguntasMenu, criar_perguntas()
    status.py      NEW   Andamento (model), HandlerAndamento, PainelAoVivo (rich), linha()
    ajuda.py       NEW   help text
    entrada.py           project/CSV choosers rewritten on Perguntas
    principal.py         menu, flows, confirmations, errors, offer of authors
```

Layers: `perguntas`, `status`, `ajuda` belong to `interface` (layer 7). No
module below `interface` imports `rich` or `questionary`; a new check in
`tests/test_camadas.py` enforces it.

## 4. Prompts (`interface/perguntas.py`)

```python
class Opcao(NamedTuple):
    rotulo: str  # text shown
    valor: str  # value returned


class Perguntas(Protocol):
    def escolher(self, texto: str, opcoes: Sequence[Opcao]) -> str: ...
    def sim_nao(self, texto: str, padrao: bool = False) -> bool: ...
    def marcar(
        self, texto: str, opcoes: Sequence[Opcao], atalhos: Mapping[str, Sequence[str]]
    ) -> list[str]: ...
    def texto(self, texto: str, validar: Callable[[str], str | None]) -> str: ...
    def mostrar(self, texto: str) -> None: ...
```

- **`PerguntasTexto(entrada: Leitor)`** — today's behaviour, generalised:
  numbered options (`1- …`), asked again on an invalid answer;
  `sim_nao` accepts `s/n/sim/não/nao/1/2`, case and spaces ignored, Enter =
  `padrao`; `marcar` reads UFs typed with commas/spaces, Enter = all, the
  atalho names (`sul-sudeste`, `todos`) expand, unknown values are named and
  asked again; `texto` repeats while `validar` returns an error message.
  EOF from `input` raises `EOFError` (unchanged, `main` handles it).
- **`PerguntasMenu(console)`** — `questionary.select`, `questionary.checkbox`
  (atalhos as the first choices; checking one ticks its UFs on submit),
  `questionary.select` with `Sim`/`Não` for yes/no, `questionary.text` with a
  validator; always `unsafe_ask()`. `mostrar` prints with `rich`.
  Constructor accepts `input`/`output` for tests.
- **`criar_perguntas(entrada)`**: `PerguntasMenu` only when `entrada is input`,
  `sys.stdin.isatty()` and `sys.stdout.isatty()`, and the environment variable
  `SAPYL_MENUS` is not `0` (escape hatch for terminals where the menus
  misbehave; documented in the README, decision §11). Otherwise
  `PerguntasTexto(entrada)`.

`main(entrada, cliente, raiz)` keeps its signature; it builds the
`Perguntas` once and passes it down. The existing `perguntar_opcao`,
`perguntar_sim_nao`, `perguntar_texto` are removed (their behaviour lives in
`PerguntasTexto`).

## 5. Quiet terminal and live status

### 5.1 Progress records (lower layers)

`registro.andamento(log, etapa, feitos, total, mensagem, *args, status=None)`
logs `mensagem` at DEBUG with `extra={'andamento': (etapa, feitos, total,
status)}`. Stages: `teste`, `busca`, `materias`, `pdfs`, `autoria`. The host
comes from the existing thread-local `casa_atual`, already set by
`execucao.por_casa`. Calls replace the per-item INFO lines listed in §2;
message texts stay the same, so the log file reads as today.

`execucao.por_casa` logs, at INFO, `Começando` when a house starts and
`Concluída` when it ends (`extra={'casa_evento': 'inicio'|'fim'}`), and tags
its periodic line with `extra={'progresso': True}`.

### 5.2 Model (`interface/status.py`)

`Andamento` (thread-safe, one lock): total houses; per house in progress its
current stage and counts; per house finished, its matters ok/erro, searches,
PDFs (from the records' `status`); run counters; start time; a rolling
history of `(time, matters done)` for the last 5 minutes.

- `HandlerAndamento(logging.Handler)` feeds records with `andamento` /
  `casa_evento` into the model (all levels, so DEBUG records count).
- Overall counters shown come from the project state through a callback
  (`progresso_das_materias`, today's function, extended to searches and
  PDFs), so a resumed run shows the project totals, not only this run's.
- **Time left** (FR-18): `calculando` until 1 minute has passed and one house
  has finished. Then: work left = matters known and not done (houses that
  finished their search) + houses not started × mean matters per finished
  house; divided by the matters-per-minute over the last 5 minutes; shown as
  `~1 h 20 min (estimativa)`. With nothing scraped yet in the window,
  `calculando`. Tested with a fake clock.
- `linha()` → the texto-mode line: today's progress line plus `tempo
  restante: …`.

### 5.3 Rendering

- **menus mode**: `PainelAoVivo` wraps `rich.live.Live` (refresh 2/s,
  transient) with a `rich.progress` bar (houses), a counters line and one row
  per house in progress (`host  matérias 45/120`). The terminal log handler is
  a `rich` handler on the same console, so INFO lines print above the panel;
  it drops records tagged `progresso` and keeps start/finish lines, warnings
  and errors. Started just before `por_casa`, stopped in a `finally` (also on
  Ctrl+C), then the summary panel is printed.
- **texto mode**: plain `StreamHandler` as today (INFO), so the terminal gets
  start/finish lines, warnings, errors and the minute line (`linha()`
  supplied as `por_casa`'s `progresso`).
- `registro.configurar(pasta, nome, modo, terminal=None)`: when the interface
  passes a handler, it is used instead of the default `StreamHandler`. The
  file handler is unchanged.

## 6. Flows (`interface/principal.py`, `interface/entrada.py`)

### 6.1 Main menu

Loop: `escolher` among `Novo projeto`, `Retomar um projeto`, `Atualizar um
projeto`, `Autoria e tramitação`, `Ajuda`, `Sair` (texto numbering 1–6).
`Ajuda` shows `ajuda.TEXTO` and loops; empty project lists say so and loop;
`Sair` returns 0. Every other choice runs once and ends the program.

### 6.2 Project lists and status (FR-4, FR-4a, FR-5)

`projeto.situacao(projeto) -> Situacao(rotulo, ultima_execucao, materias)`:

- reads the state file with `ler_csv` (latest row per stage/key) without
  opening it for writing; no state file → `não iniciado`;
- last run = newest log in `logs/` whose mode is `novo` or `retomada`
  (timestamp from the name); old projects without `logs/` use the state
  file's modification time;
- final result present and modified after that last run started → `concluído`,
  or `concluído com falhas` if the state has `erro` (matters, PDFs) or
  `incompleta` (searches); otherwise `interrompido`;
- `materias` = rows of the final result (counted without pandas, by lines),
  `?` if absent.

The list shows `nome — concluído com falhas · 28/10/2026 · 1 189 matérias`.
Status of each project is computed when the list is drawn. Update lists only
projects with a final result; authors adds `Outro arquivo CSV…` → path text
input with today's checks (`resultado_mais_recente` is kept).

### 6.3 New project (FR-6 to FR-15)

1. `ler_palavras(pasta)` and the house spreadsheet check (`EntradaInvalida`
   with the message of FR-12) **before** anything else. Keywords shown as in
   FR-13 (`descrever`).
2. Name (`texto`, no slashes, not empty). Existing name → `Retomar este
   projeto` / `Escolher outro nome` (today). No folder is created yet.
3. FR-6 houses list (only if the global table exists; date from its
   modification time; count of `ativa`).
4. FR-7 states: options = UFs in the spreadsheet (sorted), atalhos `Todos os
   estados` (empty list) and `Sul e Sudeste` (`ESTADOS_SUL_SUDESTE`).
5. FR-8 how many: count = houses of those states in the spreadsheet (or
   active houses in the reused table).
6. FR-9 PDFs.
7. FR-15 confirmation (`mostrar` the summary, then `escolher` Começar /
   Mudar respostas / Cancelar). `Mudar respostas` → back to step 3.
   `Cancelar` → return 0, nothing on disk. `Começar` → create the folder,
   `registro.configurar`, save `config.json` (`palavras`, `estados`,
   `reusar_tabela`, `limite`, `downloads`, `paralelo`), run.

`preparar_casas` filters with `filtrar_estados(casas, estados)` where
`estados = config.get('estados')`, or `ESTADOS_SUL_SUDESTE` when the config
has `sul_sudeste: true` and no `estados` (old projects). The global table is
replaced only with no state filter and `limite == '1'` (FR-11). The
`sul_sudeste` key is no longer written.

### 6.4 Resume, update, authors (FR-14, FR-16)

- `ler_paralelo` runs right after the project is chosen, before any message
  about the run (FR-14); the "Buscando os termos" line is replaced by the
  keyword list in plain words inside the confirmation.
- FR-16 short confirmation: project, status line (§6.2), keywords, PDFs;
  `Continuar` / `Cancelar`. For update: number of matters (or relevant ones)
  and PDFs; for authors: input file and number of matters.

### 6.5 After the run (FR-17, FR-21, FR-21a)

- `executar_projeto` and `executar_atualizacao` return a `Fim(texto, final,
  materias)` instead of a string. `main` prints the summary (rich panel in
  menus mode, plain in texto) and logs the same text.
- `registro.resumo` and `resumo_autoria` gain the "Próximos passos" lines,
  with the menu path of FR-17 taking the project name.
- FR-21a: if `Fim.materias > 0`, `sim_nao` (default no) with the count and
  "cerca de 2 requisições por matéria"; yes → `executar_autoria(…,
  planilha=fim.final, projeto=projeto)` (the chooser is skipped), its summary
  printed the same way. Not asked after an interruption (those paths return
  before it).
- Interrupted messages become functions of the mode and project name.

### 6.6 Errors (FR-22)

In `main`, after the existing handlers:

| Exception | Exit | Output |
|---|---|---|
| `EntradaInvalida` (keywords, spreadsheet) | 2 | its message |
| `padroes.ConfiguracaoInvalida`, `json.JSONDecodeError` on `config.json` | 2 | file path + what to fix |
| `PermissionError`, `OSError` with `ENOSPC` | 2 | file/folder and the cause in Portuguese |
| any other `Exception` | 1 | "Erro inesperado: <tipo>: <msg>. Detalhes em <log>"; traceback via `log.exception` (file only). Before a log exists, the traceback goes to `sapyl_erro_<aaaa-mm-dd_hhmmss>.log` in the working folder |

## 7. Documentation and version

README sections "Como usar" (new menu, keyword check, states, confirmation,
`SAPYL_MENUS=0`), "Retomar um projeto", "Resumo e log" (panel, status, log
lines that left the terminal); project page (`docs/`) usage section;
`tech-stack.md` (Interface row, new dependencies); version 0.4.0.

## 8. Testing (spec §7)

| Module | Covers |
|---|---|
| `test_perguntas.py` NEW | `PerguntasTexto`: invalid answers, `s/n` forms, Enter default, UF typing, atalhos, unknown UF, validator; `PerguntasMenu` through `create_pipe_input`/`DummyOutput`: select (arrows + Enter), checkbox with the `Sul e Sudeste` atalho, yes/no, text, Ctrl+C → `KeyboardInterrupt`; `criar_perguntas` choice (TTY, injected reader, `SAPYL_MENUS=0`) |
| `test_status.py` NEW | `Andamento` from synthetic log records: stages, house start/finish, counts, time left with a fake clock (`calculando`, then the estimate); `HandlerAndamento` across threads; `PainelAoVivo` rendered on a recording `rich` console (contains bar, counters, house rows) |
| `test_registro.py` | `andamento()` is DEBUG with the record; per-item lines absent from the terminal handler and present in the file; `configurar(terminal=…)`; "Próximos passos" with and without failures |
| `test_palavras.py` NEW / `test_casas.py` | `ler_palavras` errors (no file, wrong column, empty); `descrever` (single, phrase, joined terms, old query forms); `filtrar_estados`; spreadsheet check; old `limite` `'2'`/`'3'` |
| `test_projeto.py` | `situacao` for each status, including an old project without `logs/`/`config.json`; the state file is not modified by reading it |
| `test_principal.py`, `test_ponta_a_ponta.py`, `test_compat_fase1.py` | every flow scripted in texto mode (spec §7 list); early checks (exit 2, no folder); `Cancelar` leaves nothing; `Mudar respostas`; old `config.json` resumes with the same houses; FR-21a yes/no; FR-22 table. Scripts updated to the new question order; a helper `respostas_novo_projeto(...)` in `tests/apoio.py` builds the usual answers |
| `test_camadas.py` | no module outside `interface` imports `rich`, `questionary` or `prompt_toolkit` |

Every existing check (types, docstrings, no direct `requests`, network
blocked, CI on 3.10/pandas 2 and 3.12/pandas 3) keeps passing.

## 9. Implementation order

1. Dependencies, `perguntas.py` with both implementations and its tests.
2. `palavras.ler_palavras`/`descrever`, spreadsheet check, `filtrar_estados`,
   compatibility of old configs.
3. `projeto.situacao` and lazy project creation.
4. Main menu, lists, help, new-project flow with confirmation, short
   confirmations; test scripts migrated.
5. Progress records in lower layers, `execucao` start/finish lines, terminal
   handler injection.
6. `status.py` model, handler, texto line with time left.
7. Live panel and summary panel (menus mode).
8. "Próximos passos", FR-21a, interrupted messages, error table.
9. README, page, tech-stack, version; `validation.md`; validation on real
   sites with the user; merge.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Menus misbehave in some terminals (old Windows console, IDE consoles, SSH without a proper TERM) | TTY check, `SAPYL_MENUS=0` fallback, Windows check in validation |
| The live panel and log lines from 8 threads garble the terminal | One `rich` console for both; log lines printed through it; panel refresh in its own thread, model under a lock |
| Time-left estimate is wrong early in a run (big houses finish last) | Shown only after 1 minute and one finished house, marked "estimativa", based on matters per minute rather than houses |
| Changing the question order breaks the 56 scripted `main()` calls in the tests | One helper for the common answers; migrate tests in the same task as the flow change |
| Users or scripts typing today's numbers (`2` = update) | Main menu numbering changes (decision §11); README and the menu text show the new numbers; piped scripts are not a supported interface until Phase 7 |
| Reading large state files for every project in the list is slow | Read only the stage/status columns; measured in validation on the largest local project; cache per menu draw |

## 10a. Amendment (spec FR-23, FR-24), 2026-10-30

- **Voltar as an exception.** `perguntas.Voltar(Exception)`. Each
  `Perguntas` method takes `voltar: bool = False`; when true, choosing
  `← Voltar` (or `<` in texto mode, or an empty name in menus mode) raises
  `Voltar`. Flows are a list of steps run by a small loop: a step that raises
  `Voltar` moves the index back; going back from the first step leaves the
  flow (main menu, or the project list for resume/update/authors). Answers
  live in a dict, so stepping back keeps them. Return types do not change.
- **Structured counters.** The `contagens` callback returns a list of
  `(rótulo, texto)` (`Buscas`, `Matérias`, `PDFs`); the texto line joins
  them. `Andamento` gains `titulo` (header line) and `total_buscas` (active
  houses × keywords, set after the house test), and the rows in progress
  carry `feitos/total` for the per-house bar.
- **Stage lines.** `principal` logs the header block and the stage lines at
  INFO (blank lines included); `execucao.por_casa` keeps the "Começando"
  record but at DEBUG; "Concluída" becomes `✓ <host>: …`.
- Tests: every step of the new-project flow going back and forward in texto
  mode; the confirmation's Voltar; Voltar in each Perguntas method in both
  modes; the panel's sections on a recording console; the two-line texto
  block.

## 11. Decisions taken in this plan (for review)

- One `Perguntas` interface with two implementations; the mode is chosen once
  in `main`.
- Escape hatch `SAPYL_MENUS=0` (environment variable) to force numbered
  prompts. Not a CLI option, so Phase 7 is untouched.
- Main menu numbering in texto mode: 1 Novo, 2 Retomar, 3 Atualizar,
  4 Autoria e tramitação, 5 Ajuda, 6 Sair (today: 1 new/resume, 2 update,
  3 authors).
- Progress reaches the interface through log records (DEBUG + `extra`), not
  through new parameters in the lower layers.
- The project folder and its log are created only when the user confirms.
- `sul_sudeste` is still read but no longer written; `estados` replaces it.
- `executar_projeto`/`executar_atualizacao` return a small result object
  instead of the summary string.
