# Constitution — SAPyL (formerly sapl_scrap)

Non-negotiable principles for every spec, plan and change in this project.
A spec or plan that conflicts with one of these must say so explicitly and
justify the exception.

## 1. No silent data loss
- A request that fails (network error, timeout, HTTP status ≠ expected) is
  **never** recorded as if it were valid data.
- Every failure is recorded with a reason and reported at the end of a run.
- A run that finishes with failures must say so clearly; "it finished" must
  never be confused with "it got everything".

## 2. Respect the servers
- SAPL sites are public infrastructure run by small legislative houses.
  We stay within their published or observed limits (today: **35 requests per
  minute per site**).
- Limits are enforced **per site**. Speed comes from working on several sites
  at once, never from pushing a single site harder.
- `Retry-After` is always honoured.

## 3. Runs are resumable and idempotent
- Interrupting a run and starting it again must not repeat completed work nor
  duplicate results.
- Each legislative matter (*matéria*) is identified by a stable key
  (house + SAPL id), not by row position.

## 4. Tests ship with every spec
- Every spec includes automated tests (`pytest`) for the behaviour it adds or
  changes. A spec is not done until its tests pass.
- Tests run **offline**: they use saved HTML pages and fake HTTP responses,
  never the real SAPL sites.
- Real-network checks are part of a spec's *validation*, not of the test suite.

## 5. Keep it simple and usable by researchers
- The primary users are researchers, not developers. Output stays in plain
  files they can open (CSV/Excel) until a spec explicitly changes that.
- Prefer the standard library and the existing dependencies. A new dependency
  needs a reason written in the plan.
- Small, readable modules over frameworks.

## 6. Observable runs
- Progress and errors go to the terminal **and** to a log file inside the
  project folder.
- The end of every run prints a summary: what was done, what failed, where the
  results are.

## 7. Conventions
- Code identifiers, comments, user-facing messages and README are in
  **Portuguese**. Specs live in `specs/` and are written in **English**.
- Spec-driven workflow: each change lives in `specs/<yyyy-mm-dd>-<slug>/` with
  `spec.md` → `plan.md` → `tasks.md` → `validation.md`, written in that order.
- Git workflow: spec documents (`spec.md`, `plan.md`) are committed to `main`
  once the plan is finished. Implementation happens on a new branch per spec,
  which is merged into `main` only after `validation.md` passes.
- Commits do not include AI co-author trailers.
- The project is free software under **AGPL-3.0** (`LICENSE`), with credits
  in `AUTHORS.md`. New dependencies must have AGPL-compatible licenses.
