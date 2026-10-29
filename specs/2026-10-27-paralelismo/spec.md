# Spec: Parallel runs (several houses at once)

- **Status:** Approved 2026-10-27
- **Date:** 2026-10-27
- **Covers:** ROADMAP Phase 2 (Velocidade)
- **Depends on:** [2026-10-24-organizacao-e-pendencias](../2026-10-24-organizacao-e-pendencias/spec.md)
  merged into `main` after its validation
- **Principles:** [constitution](../constitution.md) · **Stack:** [tech-stack](../tech-stack.md)

## 1. Problem

A run handles one house at a time. Each SAPL site accepts 35 requests per
minute, so a house with 1 000 matters takes about 30 minutes, and a full run
over every house would take 10 to 20 hours. Most of that time the program is
waiting for one site's limit while every other site is idle.

The roadmap's answer is to work on several houses at once. A check made while
writing this spec (DNS lookups only, 2026-10-27) adds a constraint the roadmap
did not consider:

- The 10 Acre houses of the validation runs all resolve to **one address**
  (`201.54.51.178`).
- In a random sample of 60 houses from the house list, 37 resolve to that same
  address, 3 to `201.54.51.179`, and 20 do not resolve at all.
- The house list has 1 404 entries, not the ~840 the roadmap assumed.

So almost every working house sits behind the same Interlegis infrastructure.
"35 per minute per site, 20 sites at once" would send up to 700 requests per
minute to one shared server. That risks a block of our address for every
house at once, and it is not what "respect the servers" (constitution §2)
means. The per-site limit stays, and a second limit per server is added on top.

## 2. Goals

1. Several houses are processed at the same time, so a full run takes hours,
   not most of a day.
2. Every site stays within 35 requests per minute (unchanged), **and** every
   server stays within a configurable total, summed over all the houses it
   hosts.
3. If a server shows signs of strain (429 answers from several of its houses),
   the program slows down on its own for the rest of the run.
4. The results are the same as a sequential run: same rows, same order, same
   files. Resume, update and authors/procedure keep working.
5. Ctrl+C stops the whole run within a few seconds and leaves a project that
   resumes cleanly.
6. All of it is tested offline, including with real threads.

## 3. Non-goals

- Raising the per-site limit, or any per-site speed-up.
- `asyncio` / `httpx` / `aiohttp` (the roadmap's optional evolution). Threads
  from the standard library are enough for tens of houses.
- Running across several machines or processes (one process, as today).
- Command-line options (config & CLI spec). The settings are code defaults
  saved in `config.json`.
- Contacting Interlegis about acceptable load. (Considered; the user chose a
  conservative ceiling measured in validation instead.)

## 4. Users and scenarios

- **S1. Full run.** A researcher starts a new project over all houses. Several
  houses progress at once; the terminal shows which house each line is about
  and, now and then, an overall progress line. The summary also shows how long
  the run took.
- **S2. Interrupted.** The researcher presses Ctrl+C. Within a few seconds the
  program stops, prints the usual "rode de novo e escolha retomar" message, and
  a resume finishes the remaining work without repeating anything.
- **S3. Strained server.** Several houses on the same server start answering
  429. The program logs that it is slowing down for that server and lowers its
  ceiling for the rest of the run. Nothing is lost; the summary says the
  ceiling was lowered.
- **S4. Tuning by hand.** A researcher with a reason to change the defaults
  edits `paralelo` in the project's `config.json` before resuming. Invalid
  values are refused with a clear message.

## 5. Functional requirements

### 5.1 Scheduling

- **FR-1** Houses are processed by a pool of workers. Each worker takes one
  house and runs its whole pipeline: search for every keyword, then its matter
  links, its matters, and (if asked) its PDFs. A house finishes independently
  of the others, so small houses do not wait for big ones.
- **FR-2** The number of houses worked on at once has a code default (§5.4),
  at least 1. With 1, the run behaves exactly like today's sequential run.
- **FR-3** The availability test of the houses (when the table is not reused)
  also runs in parallel, under the same limits.
- **FR-4** Update mode (re-scrape a final table) and authors/procedure (option
  3) use the same pool, per house.

### 5.2 Limits

- **FR-5** The per-site limit is unchanged: at most 35 requests in any 60 s
  window plus the 1 s margin, per host, across runs (history on disk), with a
  429 blocking that host for `Retry-After`.
- **FR-6** A **server** is the IP address a house's host resolves to, looked
  up once at the start of a run. Hosts that do not resolve get no server (they
  fail with `dns` anyway). Every request also counts against its server's
  window: at most `limite_por_servidor` requests in any 60 s window plus the
  margin. A request waits until **both** its site and its server allow it.
- **FR-7** The server windows are saved in the same history file as the site
  windows, so a resumed run (or another project started right after) does not
  exceed the server total either.
- **FR-8** Adaptive slow-down: if, within 10 minutes, houses on the same server
  answer 429 from at least 2 different hosts, that server's ceiling is halved
  for the rest of the run (never below 35, one house at full speed). Each
  change is logged as a warning and mentioned in the summary.

### 5.3 Results, state and output

- **FR-9** The final table has the same rows in the same order as a
  sequential run: houses in the house-table order, then matters in their
  first-found order. Other files may get their lines in a different order
  (they are append-only logs of work done); nothing reads them by position.
- **FR-10** Writing to shared files (state, search pages, links, matters,
  authors partial file, cache, request history) is safe with several workers:
  no line is lost, cut or mixed with another.
- **FR-11** The links of each house are deduplicated within that house (keys
  are per host, so this equals today's global deduplication). The links file
  keeps today's format; a project resumed from spec 2 reads it as today.
- **FR-12** Ctrl+C: workers stop taking new work, requests in flight finish or
  time out, and the program exits within the request timeout (≤ 30 s, usually
  a few seconds). Every finished item is already in the state file, so a
  resume continues from there.
- **FR-13** Terminal output: each progress line names its house
  (`[sapl.x.leg.br] Matéria 3 de 120: …`). Every 60 s an overall line shows
  houses done / in progress / waiting, matters scraped and errors. The log file
  keeps every line, including one DEBUG line per request, as today.
- **FR-14** The summary adds: elapsed time, houses processed in parallel, and,
  per server, the ceiling used (and whether it was lowered).

### 5.4 Settings

- **FR-15** Defaults in one place in the code: `casas_ao_mesmo_tempo` and
  `limite_por_servidor`. Starting values: 8 houses and 120 requests/min per
  server. Validation (§8) measures them on the real sites and sets the final
  defaults.
- **FR-16** A new project saves them in `config.json` under `paralelo`. A
  project from an older version has no `paralelo` key and uses the defaults.
  Hand-edited values are checked when the run starts: whole numbers,
  `casas_ao_mesmo_tempo` ≥ 1, `limite_por_servidor` ≥ 35. A bad value stops the
  run before any request, with a message naming the key and the allowed range.

## 6. Testing

Offline, with the existing helpers. Concurrency is tested with real threads.

- **TR-1** Limiter, single thread, fake clock: site and server windows both
  hold; a request waits for the stricter of the two; history saves and loads
  server windows.
- **TR-2** Limiter under threads: many workers hammering a fake SAPL with
  several hosts on one fake server. In the recorded send times, no host
  exceeds 35 and no server exceeds its ceiling in any window. These tests use a
  scaled-down window (fractions of a second) so they run fast; the window
  length is a parameter of the client.
- **TR-3** Adaptive slow-down: 429s from 2 hosts of the same server halve its
  ceiling once; from 1 host they do not; the floor is 35.
- **TR-4** Equivalence: the same fake run with 1 worker and with 8 workers
  gives byte-identical final tables (apart from `raspada_em`), the same state
  contents and the same downloads.
- **TR-5** Interruption: Ctrl+C (a `KeyboardInterrupt` raised in the main
  thread while workers run) stops the run; the resume finishes it with the
  same result as an uninterrupted run, and no item is requested twice except
  the ones in flight at the interruption.
- **TR-6** Shared files: workers appending at the same time never produce a
  short, joined or duplicated line (each file read back gives the expected
  rows).
- **TR-7** Settings: defaults, saved in new projects, old projects without
  `paralelo`, invalid values refused before any request.
- **TR-8** The end-to-end test runs with several workers and checks per-site
  and per-server limits from the recorded send times.

## 7. Non-functional requirements

- **NFR-1 Dependencies.** Standard library only (`threading`,
  `concurrent.futures`, `socket`).
- **NFR-2 Compatibility.** Projects and files from spec 2 resume, update and
  run option 3 unchanged. Output formats unchanged.
- **NFR-3 Speed.** On the 10 Acre houses (3 keywords), the run is limited by
  the slowest house and the server ceiling, not by the number of houses (target
  in §8).
- **NFR-4 Docs.** README (what runs in parallel, `paralelo` in `config.json`,
  the server ceiling and why), tech-stack, ROADMAP ticks, the project site's
  "Quanto tempo leva?" section.

## 8. Acceptance criteria

1. Offline suite and CI green; coverage stays ≥ 95 %.
2. Real run on the 10 Acre houses with `casas_ao_mesmo_tempo` = 8 and
   `limite_por_servidor` = 120: from the logs, no host above 35 and the server
   above 120 in any 60 s window; zero 429s, or a logged slow-down with no data
   lost.
3. The same run's final table has the same keys and statuses as a sequential
   run made the same day (differences only from matters changed on the sites in
   between).
4. Ramp: runs at ceilings 120, then 175 (5 houses at full speed), recording
   429s and response times. The final defaults are set from this, and written
   in the validation file with the numbers that justify them.
5. Ctrl+C during the parallel run, then resume: finishes with the same keys as
   criterion 3.
6. Update mode and option 3 work in parallel on the validation project.

## 9. Open questions

- **Q1. Final defaults.** 8 houses and 120 requests/min per server are
  starting values, to be confirmed or changed by the validation ramp (AC 4).
- **Q2. Server = IP address.** Two IPs (`.178` and `.179`) look like the same
  provider. Treat them as one server (stricter) or two? The draft treats each
  IP as a server; the ramp can show whether `.179` behaves independently.
