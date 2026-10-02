## What's in v0.1.1

A step-by-step interview that asks one section at a time, plus direct ingestion of grid, table, and keyword files.

### Added

- **Deterministic interview engine** — a 23-question catalogue across 7 sections, plus dynamic per-well questions. Pure functions over `(spec, answers)`, no server-side session: the client owns the answers dict and round-trips it, so a reload resumes exactly where you left off.
- **File and paste ingestion** — GRDECL/SPECGRID fragments, `PORO`/`PERMX` arrays, numeric grids, and PVDG/PVT tables. The format is detected and folded into the spec; upload and paste produce byte-equal specs. Genuine per-cell variation is refused by name rather than silently mean-averaged.
- **Stateless HTTP surface** — `POST /api/interview/next`, `/api/interview/finish`, `/api/ingest/parse`, `/api/ingest/upload`.
- **InterviewPanel in the Deck Builder** — progress bar, answer/skip per question, restart, build-from-answers.
- **Semantic validation surfaced inline** — a gas cap declared without a GOC depth, a well placed deeper than the grid, or a `dz` list whose length disagrees with `nz`.

### Fixed

- EQUIL datum depth was pinned to the SPE1 default (8400 ft) regardless of the grid. It is now clamped to the grid midpoint when that default falls outside the model span; default decks stay byte-identical.
- `ReservoirSpec.dx/dy` accepted lists but `base.j2` string-multiplied them and the METRIC conversion multiplied a list by a float.
- `field_units=False` was silently ignored and every deck rendered FIELD. METRIC without a fluid descriptor is now refused rather than shipping wrong-unit PVT.
- The tokenizer classified bare-exponent (`1E5`, `3E-6`) and Fortran D-exponent (`2.5D+01`) real literals as UNKNOWN, silently discarding them from real exports.
- `use_llm` was ignored on the REST build path.
- The fluid branch of `_compute_template_context` was stranded as dead code when the METRIC guard was added as an `elif` after a two-line header, which silently pinned every deck with a fluid descriptor to the hardcoded SPE1 PVT tables.
- Restart in the interview panel cleared state without refetching, leaving the panel blank with progress stuck at the pre-restart count.
- `detect_format` uppercased the entire upload but only inspected the first 200 characters, doubling peak memory on a 256 MB file.

### Design invariants

- **Never breaks** — every question is skippable, and a skip records the declared default server-side, so the terminal state always builds a deck.
- **Stateless** — no server-side session; the client owns the answers.
- **Provenance triad only** — every value is tagged `extracted`, `defaulted`, or `user_override`.
- **Never mean-average** — per-cell variation is refused by name.

### Verification

- 940 passed, 2 skipped (13m28s full suite)
- `tsc --noEmit` clean, frontend self-check suite green
- Browser sweep across all 9 routes: no console errors, no failed requests, no HTTP >= 400
- Interview panel walked end to end in Chromium: answer, skip, non-numeric rejection, paste, upload, build, restart, collapse/expand, reload-resume — 11/11

### Fixes found by code review

- Picking a scenario could deadlock the interview: `/interview/next` evaluated the catalog against the extraction-only spec, so "gas cap" never made the GOC question reachable while rule R04 blocked on a missing one and finish returned 422 with no answer available. The engine now folds collected answers before evaluating the catalog, iterating to a fixed point because an answer can change applicability. All seven scenarios reach a lint-passing deck.
- The RSVD clamp was dropped alongside the METRIC guard, leaving its comment behind with no statement — every deck with a fluid descriptor rendered the hardcoded SPE1 value of 1.27.
- `detect_format` sniffed for a numeric grid before the leading keyword, so a `PERMX` fragment written one value per line was read as a grid and its permeability written into porosity as 100.0. The linter only warns on that, so the deck still linted clean.
- Result-file rejection matched substrings, so `INIT` matched the word "initial" and a paste headed with `-- initial porosity estimate` was refused as an unreadable EGRID.
- The no-DIMENS ingest path used `sorted(set(...))`, silently re-ordering a layer profile (500/100/200 became 100/200/500).
- `apply_ingest` dropped patch keys the model does not carry, so a SWOF table parsed fine and was then discarded while the UI reported success.
- Wells were never asked their type, leaving the "waterflood with no injector" block with no available answer; per-well type questions now exist.
- R02's datum fallback disagreed with the builder's own clamp, and R07 checked only the upper grid bound, so an index of 0 passed.
- The persisted interview answers included the whole ingested file text, exceeding the localStorage quota on a large upload.

### Note on the changelog

`CHANGELOG.md` carries a `0.2.0` block written ahead of a release that was never tagged or cut. `v0.1.0` was the last real tag, so this ships as `v0.1.1`; the `0.2.0` notes are retained as a record of work that landed before it.
