# OPM-AI Progress Report

Date: 2026-07-19. Scope: full audit + debug + dataset-learning pass over
everything built so far, measured against the AIM.

## 1. The aim, restated

An AI layer on top of open-source reservoir simulators (OPM Flow) so students,
researchers and faculty can understand and teach reservoir simulation through
simple chats - plain English in, valid deck + run + visualization + explanation
out; open source, offline-first, one `docker compose up`.

## 2. Where we are against the plan

| Part | Spec doc | Status |
|------|----------|--------|
| Stage 0 skeleton/settings | 00 | DONE (committed) |
| Part 1 Runner | 01 | DONE + hardened this pass |
| Part 2 Linter | 02 | DONE + calibrated twice against Flow ground truth |
| Part 3 Builder+LLM+CLI | 03 | DONE (offline path); LLM extraction = Phase 2 stub |
| Part 5 Postprocess | 05 | Reference sketch; works on SPE1 end-to-end; Stage 4 gaps inventoried below |
| Part 6 API + frontend | 06 | NOT STARTED (empty `opm_ai/api/`, no `frontend/`) |
| Part 4 Preprocess PVT | 04 | NOT STARTED |
| Part 7 Explainer/RAG | 07 | NOT STARTED (Phase 3 by design) |
| Part 8 Deployment | 08 | NOT STARTED (no Dockerfile/CI yet) |

Suite: 66 passed / 0 failed. Working pipeline today:
`plain English -> ModelSpec -> deck -> lint -> flow run -> DataFrame/KPIs/plots`.

## 3. What the audit found and what was fixed (this pass)

Five Sonnet audit agents (runner, linter, builder+CLI, llm+settings+packaging,
postprocess) + three simulation-sweep agents ran against the working tree.
Confirmed findings were fixed and committed; each fix was verified empirically.

### Fixed
- **Runner**: crash-report parser only read lines containing `Error:`, so
  Flow parse diagnostics (`Problem with keyword X`, `In <deck> line N`) never
  yielded keyword/line. Now parses PRT (primary) + all stderr. SimulationResult
  gained the spec extras: `timed_out`, `duration_s`, `stdout`, `stderr`,
  `warnings`, `summary_files`, `prt_path`. Never-raise invariant preserved
  (mkdir moved into try).
- **LLM client determinism**: presence of API keys in a CWD `.env` silently
  enabled network calls - `lint_deck` cost 1-2s in the repo root and 4ms
  elsewhere. Now gated on `LLM_PROVIDER` opt-in (default `offline`); NVIDIA NIM
  wired as a provider (`nim`) - its key was previously loaded but unused.
- **Builder extraction**: plain "waterflood"/"water injection" now maps to the
  5-spot scenario (previously fell through to depletion); rates parsed
  ("produce at 2000 stb/day", "inject 8000 bbl/day"); word-form well counts
  ("two producers"); explicit counts override scenario patterns ("one injector
  and one producer" waterflood = 2 wells, not 5).
- **Linter, two calibration rounds** (see section 4).

### Known limitations (documented, not bugs)
- Builder scenarios co2/gas_cap/multilayer/buildup render as depletion-like
  producer-only decks; WAG has no alternation schedule. v1 is depletion-first
  by design; scenario templates are the Phase 2 roadmap (03-builder.md).
- `build_deck(use_llm=True)` is a stub until Phase 2.
- Audit claims NOT reproduced (checked before fixing): "EQLDIMS missing breaks
  full runs" and "TSTEP causes invalid timeStep" - a fresh generated deck runs
  fine (exit 0, 16 report steps); "5-spot injector completed only in layer 1" -
  extract.py sets k1=1,k2=nz. Treat those agent reports as false alarms.

## 4. Linter calibration: the headline numbers

Ground truth = `flow --enable-dry-run=true` exit code on every fixture deck,
run from the deck's own directory. Confusion matrix over the corpus
(spe1, spe1_brine, spe3, spe5, wconprod, mult, pinch; 133 decks):

| | initial audit | after round 1 | after round 2 + IMPORT fix |
|---|---|---|---|
| False positives (lint blocks a Flow-valid deck) | 77 | 54 | **0** |
| True negatives | 42 | 54 | 122 |
| False negatives (lint passes, Flow rejects) | 7 | 6 | 9* |
| True positives | 4 | 2 | 1 |

*FNs are runtime/parser failures an offline linter cannot see: WCONPROD enum
values inside record data (6 decks), AQUFET record parsing, missing restart
file, ENDSCALE value validation. Candidates for a deep-parse mode
(`opm.io.Parser` behind `OPM_LINTER_DEEP`), not for regex rules.

What round 2 taught us (now encoded in rules + context.md):
- Data live in INCLUDE/IMPORT files constantly: PROPS tables, whole sections
  (SPE5), grids (EGRID via IMPORT). Every "required X missing" rule must skip
  or downgrade when includes are present.
- Wells are declared incrementally: multiple WELSPECS blocks per SCHEDULE;
  cross-reference rules must scan all occurrences.
- WCONHIST/WCONINJH are accepted alternatives to WCONPROD/WCONINJE.
- Flag keywords with no terminator: THERMAL, TEMP, RADIAL, BLACKOIL, BRINE,
  NEWTRAN, ENDBOX, FILLEPS, NOINSPEC, NORSSPEC, SKIPREST.
- A keyword line contains ONLY the keyword; matching loosely turns data lines
  (`BASIC = 2` inside RPTRST) into phantom keywords.
- PVTWSALT is the brine variant of PVTW.

## 5. What the simulation sweeps taught us

### SPE1 family (25 decks, full physics runs)
19/25 complete with SMSPEC+UNRST; failures are genuinely unsupported physics
(thermal+MSW combination), a malformed AQUFET fixture, and a restart deck
without its restart file. Postprocess `read_summary`+`extract_kpis` worked on
every representative output tested (base, thermal, MSW), e.g. SPE1CASE2_MSW:
51.7 MMSTB field oil, plateau 1610 days over a 10-year run.

### Keyword families (wconprod, spe3, spe5, spe9, wvfpexp, operate, actionx)
- SPE3 (gas cycling, VAPOIL) and SPE9 (corner-point + INCLUDEs) run clean.
- WCONPROD-01..05,11 pass dry-run but fail FULL runs ("Well control must be
  specified") and -06..10,12 fail even dry-run on enum values - these fixtures
  are intentional negative tests of WCONPROD variants. Lesson recorded: even
  Flow's own dry-run does not catch everything; full-run gating matters.
- Catalog of deck features our builder never emits and linter has no rules
  for (= future scenario/rule roadmap): VFP tables (VFPPROD/VFPINJ), ACTIONX,
  OPERATE, GCONPROD/GCONINJE group control, WECON/WELTARG, DATES schedules,
  wildcard well names (`OP*`), INCLUDE-modular decks.

### Builder scenario matrix (10 cases to 12,800 cells, full physics)
- All 10 lint clean and run to completion; runtime 0.16-1.15s, ~O(N^1.2).
- Physics sanity: waterflood produces 4x depletion oil on the same grid
  (1.44 vs 0.36 MMSTB) - qualitatively correct.
- Degenerate outcomes found and worth designing against in Phase 2 templates:
  depletion recovery is BHP-limited so identical across grid sizes; no water
  breakthrough within the default 720-day horizon (short horizon + top-layer
  gas injector at (1,1) vs bottom-layer producer in the SPE1-like pairing
  gives poor connectivity); WAG lacks an alternation schedule.

## 6. Debt register (carried forward)

1. Postprocess Stage 4 gaps (from spec 05): field-level KPIs
   (FOPT/FWPT/FGPT-based recovery, max watercut, breakthrough day), per-producer
   KPI naming, plot_production well-level fallback (currently 1 trace instead
   of 3 when field totals absent), watercut -0.0 vs NaN.
2. Builder Phase 2: scenario-specific templates (WAG cycles, gas-cap EQUIL,
   CO2 stream), METRIC units, calendar-month TSTEP or DATES, LLM extraction.
3. Linter: deep-parse mode for the 9 FN classes; INCLUDE resolution;
   rules for GCONPROD/VFP/ACTIONX families.
4. NOECHO/ECHO in base.j2 draw "not supported" warnings from Flow - harmless,
   remove when next touching the template.
5. Stages 5-8 (API, frontend, preprocess, deployment) not started.

## 7. Suggested next stage

Stage 4 (postprocess to spec) is the highest-leverage next step: the sweeps
show the simulation and KPI layers already mostly work, and closing the KPI/
plot gaps unlocks the FastAPI backend (Stage 5), which consumes exactly those
functions.
