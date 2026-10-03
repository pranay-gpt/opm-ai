## What's in v0.1.1

A step-by-step interview that asks one section at a time, plus direct ingestion of grid, table, and keyword files — and now a published Docker image, so students can run the whole workbench without installing anything.

### Run it

```bash
docker run -d --name opm-ai -p 8000:8000 \
  -v ./decks:/app/decks -v ./results:/app/results \
  ghcr.io/pranay-gpt/opm-ai:v0.1.1
# open http://localhost:8000
```

Multi-arch (linux/amd64 and linux/arm64), published automatically by GitHub Actions on every `v*` tag. Both `v0.1.1` and `0.1.1` tags exist, plus `latest`. The image bundles the FastAPI backend, the built React frontend, OPM Flow itself, and every Python dependency; nothing is installed on the host beyond Docker.

### Added

- **Deterministic interview engine** — a 23-question catalogue across 7 sections, plus dynamic per-well questions. Pure functions over `(spec, answers)`, no server-side session: the client owns the answers dict and round-trips it, so a reload resumes exactly where you left off.
- **Published multi-arch Docker image** — `.github/workflows/docker-publish.yml` builds `linux/amd64` and `linux/arm64` on native GitHub runners (no QEMU), pushes each by digest, and merges a manifest list. Tag pushes publish the version tag; pushes to `main` publish `:main`. No secrets: `GITHUB_TOKEN` only, since the repo is public.
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

- 966 passed, 2 skipped (13m38s full suite)
- `tsc --noEmit` clean, frontend self-check suite green
- Browser sweep across all 9 routes: no console errors, no failed requests, no HTTP >= 400
- Interview panel walked end to end in Chromium: answer, skip, non-numeric rejection, paste, upload, build, restart, collapse/expand, reload-resume — 11/11
- **In-container** (arm64, built from this tree): smoke 7/7; all 7 interview scenarios reach a terminal state with a lint-passing deck; one real OPM Flow run (`flow 2026.04`) writing all 8 output files; browser pass with zero console errors
- **From the published image** pulled back off GHCR: health ok, version 0.1.1, `flow --version` present, smoke 7/7, `./decks` bind-mount round-trips to the host

### Docker packaging fixes

- The image now installs `jq`. `scripts/smoke.sh` asserts with it, so without it the in-container smoke failed its own health check even though the app was healthy.
- The image now creates `/app/decks` and `/app/results`. Compose bind-mounted them, but a plain `docker run` (the documented student path) did not, and a build with an explicit `output_path` returned 500 ENOENT.
- The publish workflow's digest artifact was named from `matrix.platform` (`linux/amd64`), and artifact names cannot contain a slash, so the upload failed and the manifest merge never ran. The platform is now slugged into the name.
- The workflow stripped the leading `v` from the version, so `:0.1.1` existed while the README documented `:v0.1.1`. Both tags are now published.

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
