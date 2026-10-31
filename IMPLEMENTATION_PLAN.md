# Reservoir-Context-Aware Builder

Branch: `feat/reservoir-context-builder`

Feature: after the initial prompt, the builder asks relevant step-by-step questions about
each section (grid, rock, fluid, equil, wells, schedule) before building. Also supports
direct upload or paste of input files (grid files, tables, keyword exports) which get parsed
into the spec.

Full design: `.claude/jobs/` session tmp `design.md` (persisted copy of the research
workflow synthesis, runId wf_98eb33d6-42c). Research reports: formats / elicitation /
integration / llm-extraction / domain / stability.

## Stage 1 — Fix the four builder defects (no new features)

- B1: `equil_goc_depth` renders EQUIL item 5, not item 4 (GOC). `builder.py` assigns to
  template var `equil_owc_depth`; `base.j2` renders `equil_goc` there. Assign to `equil_goc`.
- B2: datum/WOC depths hardcoded to SPE1 and do not follow `top_depth`; the
  `context.get("equil_datum_depth", ...)` fallback is dead. Derive from `top_depth`/`sum(dz)`.
- B3: `ReservoirSpec.dx/dy` accept lists but `base.j2` does `(dx ~ ' ') * (nx*ny*nz)` and
  `_compute_metric_context` multiplies list by float. Mirror the `dz_list` branch for dx/dy.
- B4: honour `spec.field_units` (currently hardcoded `unit_system = "FIELD"`).
- Widen linter v2 tokenizer `_REAL_RE` for bare-exponent (`1E5`) and Fortran `D`-exponent
  (`2.5D+01`) forms.

Each fix gets a regression test that fails before the fix. Verify: full suite passes.
Commit: one commit per defect.

## Stage 2 — Wire use_llm on the REST build path

`extract_parameters_llm_with_provenance()` in builder/extract.py, mirroring the offline
pair. `routes/build.py` dispatches on `request.use_llm` and merges over the offline spec.
LLM-supplied fields are provenance `extracted`.
Verify: existing POST /api/build tests unchanged; new test with a scripted fake client.
Commit: feat(build): honour use_llm with provenance.

## Stage 3 — Question catalog + engine (pure, no HTTP)

`opm_ai/builder/interview/catalog.py` (Question dataclass + CATALOG list),
`engine.py` (`next_question`, `apply_answer`, `build_spec`, `apply_defaults_for_rest`),
`rules.py` (`validate(spec) -> list[Finding]`). Stateless: the client owns `answers`.
Every question skippable; skipped answers record the declared default. The LLM is never on
the critical path. Reuse the provenance triad (extracted/defaulted/user_override) only.
Verify: tests/unit/test_interview_engine.py, no FastAPI, no LLM.
Commit: feat(builder): deterministic interview engine.

## Stage 4 — Ingestion via the linter v2 parser

`opm_ai/builder/interview/ingest.py`: `parse_paste(text) -> IngestResult`, never raises.
Detection: full deck vs bare GRDECL fragment vs PVT/relperm table vs plain numeric grid.
Uniform/per-layer only; refuse genuine per-cell variation with the array named; refuse
EQUALREG/ADD/MULTIPLY (not evaluated) and EGRID (result file). Reuse upload.py's
`_safe_relpath`, MAX_PART_SIZE, MAX_FILES security model. Paste and upload must produce
byte-equal specs.
Verify: tests/unit/test_ingest.py + tests/fixtures/interview/.
Commit: feat(builder): parse pasted and uploaded keyword files into the spec.

## Stage 5 — HTTP surface — DONE (7a84dbf)

`api/schemas.py`: QuestionDTO, InterviewRequest/Response, FinishRequest/Response,
IngestRequest/Response.
`api/routes/interview.py`: POST /api/interview/next (stateless, returns next question +
progress + findings + resolved), POST /api/interview/finish.
`api/routes/ingest.py`: POST /api/ingest/parse (JSON text) and POST /api/ingest/upload
(multipart) — both call `parse_paste`, so they are byte-equal by construction.
`api/server.py`: register routers. POST /api/build untouched.
Verify: tests/integration/test_api_interview_ingest.py (14 tests) + a live-server
end-to-end walk (23 questions asked, lint passed, PORO ingest mapped to porosity).
Note: finish applies answers BEFORE validate, so a wrongly answered blocking question is
a 422 while a skipped one records the declared default and still builds.

## Stage 6 — Frontend — DONE (0a88d65)

`useAppStore`: interview slice in the persist slice (answers + panel visibility persisted;
the question itself is re-fetched on mount). `client.ts`: interviewNext / interviewFinish /
ingestParse / ingestUpload wrappers reusing fetchJson / fetchMultipart. New
`InterviewPanel.tsx`: Answer / Skip / Restart, progress bar, file picker + paste box;
mounted in DeckBuilder above the Build button. No change to RockBasicsSection.
Verify: `npm test` (7 suites, new interviewClient.test.ts appended to the chain),
`tsc -b` clean, eslint clean on the new files. The 4 pre-existing eslint errors in
DeckBuilder.tsx / useAppStore.ts date from an earlier commit and were left alone.

## Explicitly skipped

| Skipped | Add when |
|---|---|
| Server-side interview sessions | never - stateless + zustand persist covers reload/retry |
| Per-cell property arrays in ReservoirSpec | a real static-model use case arrives |
| GRDECL output via INCLUDE | never - breaks /api/decks, browser download, lint |
| opm.io parsing | never - not in container venv; aborts process on bad INCLUDE |
| Per-step LLM calls | a measured gap the regex extractor and parser both miss |
| EGRID as an input | never - result file with no petrophysics |
| Server-side interview session store | never - the client round-trips the answers dict |
| New provenance tag for ingested data | never - ingested values are `extracted` (they came from a source) |
| INCLUDE-based GRDECL in the generated deck | never - breaks /api/decks, browser download, lint |
