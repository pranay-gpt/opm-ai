# OPM-AI: Context for New Sessions

Last updated: 2026-07-19  
Status: Parts 1-3 complete and hardened; Parts 4-8 not started  
Suite: 66 passed / 0 failed

## What This Is

OPM-AI is an AI-assisted reservoir simulation workbench for petroleum engineering education. Vision: user types plain English ("10x10x3 grid, one injector one producer, 5-year waterflood, API 35 oil"), system converts it to an Eclipse .DATA deck, runs OPM Flow, and returns visual results + educational explanations. Open source, offline-first, single `docker compose up`.

## Where We Are (Progress Against the 8-Part Plan)

| Part | Spec | Status | Test Coverage |
|------|------|--------|---------------|
| 0 | skeleton/settings | ✅ DONE | settings unit tests |
| 1 | Runner (OPM Flow wrapper) | ✅ DONE + hardened | 8 integration tests (SPE1, edge cases, timeout, missing binary) |
| 2 | Linter (deck validation) | ✅ DONE + calibrated | 14 unit tests + dataset validation (133 fixtures, FP=0) |
| 3 | Builder+LLM+CLI | ✅ DONE (offline path) | 8 integration tests (scenarios + grid sweep) |
| 4 | Preprocess (PVT/relperm) | ❌ NOT STARTED | - |
| 5 | Postprocess (ResInsight/plots) | 🟡 Reference sketch | works on SPE1; Stage 4 gaps known |
| 6 | API + React frontend | ❌ NOT STARTED | `opm_ai/api/` empty, no `frontend/` |
| 7 | Explainer/RAG | ❌ NOT STARTED | Phase 3 by design |
| 8 | Deployment (Docker/CI) | ❌ NOT STARTED | no Dockerfile yet |

**Working pipeline today:** plain English → ModelSpec → .DATA deck → lint → flow run → DataFrame/KPIs/plots

## Critical Knowledge (Read Before Changing Anything)

### Runner (`opm_ai/runner/`)
- **Never-raise invariant**: `run_simulation()` returns `SimulationResult` with `success=False` and `crash_report` on ANY failure; never throws.
- Flow invocation: `flow DECK.DATA --output-dir=DIR --enable-dry-run=true|false`. Do NOT use bare `--check` (broken in 2026.04).
- `--threads` flag omitted due to compatibility issues per 01-runner.md.
- Crash report parser reads PRT file first (primary), then stderr; searches all lines (not just lines containing "Error:").
- Exit codes: 0=success, 1=handled error, 134=SIGABRT, 141=SIGPIPE (harmless).
- Timeout: uses `subprocess.run(timeout=T)`, checks for zombie processes.
- Contract fields: `success`, `output_dir`, `crash_report`, `returncode`, `timed_out`, `duration_s`, `stdout`, `stderr`, `warnings`, `summary_files`, `prt_path`.

### Linter (`opm_ai/linter/`)
**Read `opm_ai/linter/context.md` BEFORE touching any rule.** Key invariants:

1. **Offline-first**: must run in CI without OPM install or API key. Rule engine is pure Python; LLM is additive.
2. **Calibration invariant**: ERROR flips `passed`, so every ERROR rule must be calibrated against Flow ground truth (`flow --enable-dry-run=true` exit 0). Current state: **0 false positives** over 133 fixture decks.
3. **INCLUDE/IMPORT handling**: v1 does not resolve includes or binary EGRID imports. Rules skip or downgrade to WARNING when includes are present (data/sections may come from external files).
4. **Regex pitfall**: use `\Z` (end of string), NOT `$` (end of line in MULTILINE mode). `$` truncates extraction to first data row.
5. **Incremental declarations**: wells/tables can be declared multiple times (e.g., second WELSPECS block at later TSTEP). Cross-reference helpers scan ALL keyword occurrences via `re.finditer`, not just `re.search`.
6. **Terminator detection**: `/` anywhere on a line (after stripping quotes and `--` comments) terminates the record; Eclipse ignores trailing text.
7. **Flag keywords** (no data, no `/`): THERMAL, BLACKOIL, TEMP, RADIAL, BRINE, NEWTRAN, ENDBOX, FILLEPS, NOINSPEC, NORSSPEC, SKIPREST.
8. **History controls**: WCONHIST/WCONINJH accepted as alternatives to WCONPROD/WCONINJE.
9. **Regression guard**: `tests/integration/test_dataset_validation.py` asserts known-good fixtures pass lint. Run this BEFORE tightening any ERROR rule.

Rule IDs: L001 (missing `/`), L003/L003b (grid), L004 (negative perm), L005 (phase/PROPS), L006-L008 (well cross-refs), L009 (SOLUTION), L010 (SUMMARY), L011 (PORO range), L012 (SATNUM), L013 (keyword order), L014 (INCLUDE depth), L015 (DIMENS).

### Builder (`opm_ai/builder/`)
- Entry: `build_deck(description, use_llm=False) -> DeckGenerationResult`. Offline path (use_llm=False) works end-to-end; LLM extraction is Phase 2 stub.
- Pipeline: description → `extract_reservoir_info()` → ModelSpec → `render_template()` → .DATA text → `lint_deck()` → `build_summary()` → DeckGenerationResult.
- Template: `templates/base.j2` (Jinja2), controlled by ModelSpec fields.
- Scenarios: depletion (default), waterflood_5spot, waterflood_line_drive, wag, gas_cap, co2_injection, multilayer, buildup. Note: co2/gas_cap/multilayer/buildup currently render as producer-only depletion-like decks (scenario templates are Phase 2 roadmap).
- Extraction: regex + keyword matching on plain English. Waterflood detection: "waterflood", "water injection", "water flood". Rate parsing: "produce at 2000 stb/day", "inject 8000 bbl/day". Word-form counts: "two producers", "three injectors". Well placement: gridded patterns per scenario enum.
- Units: FIELD only (v1 scope per 03-builder.md).
- Linter auto-runs; if `passed=False`, deck is None and warnings list the issues.

### LLM Client (`opm_ai/llm/`)
- **Opt-in only**: network calls gated on `LLM_PROVIDER` setting (default: `offline`).
- Providers: `groq` (Llama-3.3-70B-versatile), `nim` (NVIDIA NIM), `openai`, `offline`.
- `LLMClient.available` property tells you if the client has a working backend.
- `summarize_issues(issues)` returns `str | None` (None when offline).
- Keys: `GROQ_API_KEY`, `NVIDIA_API_KEY`, `OPENAI_API_KEY` (`.env` or env vars).

### Settings (`opm_ai/settings.py`)
- Uses pydantic-settings with `.env` auto-load.
- Key settings: `OPM_FLOW_BINARY` (default `/usr/bin/flow`), `LLM_PROVIDER` (default `offline`), `OFFLINE_MODE` (deprecated, use LLM_PROVIDER).
- Changing `OPM_FLOW_BINARY` at runtime requires module reload or restart (cached at import).

## Debt Register (Known Gaps)

1. **Postprocess Stage 4 gaps** (spec 05-postprocess.md): field-level KPIs (FOPT/FWPT/FGPT recovery, max watercut, breakthrough day), per-producer naming, `plot_production` well fallback (1 trace vs 3), watercut -0.0 vs NaN.
2. **Builder Phase 2** (spec 03-builder.md): scenario-specific templates (WAG alternation, gas-cap EQUIL, CO2 stream), METRIC units, DATES schedules, LLM extraction (`use_llm=True` end-to-end).
3. **Linter future**: deep-parse mode for the 9 FN classes (runtime/parser errors), INCLUDE resolution, rules for GCONPROD/VFP/ACTIONX families.
4. **Template cleanup**: NOECHO/ECHO in base.j2 draw "not supported" warnings from Flow (harmless, remove when next editing).
5. **Stages 4-8**: Parts 4 (preprocess), 5 (API backend), 6 (React frontend), 7 (explainer/RAG), 8 (deployment) not started.

## What the Last Audit Found (2026-07-19)

5 Sonnet agents audited runner/linter/builder/llm/postprocess + ran simulation sweeps over 133 fixture decks and 10 builder scenarios. Fixed:
- Runner crash-report parser (PRT + all stderr, not just "Error:" lines)
- LLM client determinism (opt-in gating + NVIDIA NIM wiring)
- Builder extraction (waterflood keyword, rate parsing, word-form counts)
- Linter calibration (2 rounds): FP count 77 → 54 → 0 over 133 decks

Linter confusion matrix (final):
- TN: 122 (lint pass, Flow pass)
- FP: 0 (lint fail, Flow pass) ← **calibrated to zero**
- FN: 9 (lint pass, Flow fail) ← runtime errors an offline linter can't catch
- TP: 1 (lint fail, Flow fail)

Simulation sweeps: 25/25 SPE1 family decks run (19 produce SMSPEC+UNRST); 10/10 builder scenarios run to completion (runtime ~0.16-1.15s, scales O(N^1.2)); waterflood produces 4x depletion oil on same grid (physics qualitatively correct).

## How to Continue Development

### Before touching the linter
1. Read `opm_ai/linter/context.md` (the calibration knowledge).
2. If tightening an ERROR rule, run `pytest tests/integration/test_dataset_validation.py` first to catch regressions.
3. Ground truth is `flow --enable-dry-run=true --output-dir=DIR DECK` exit code, run FROM the deck's directory.

### Before touching the runner
- Preserve the never-raise invariant (return `SimulationResult` with `success=False`, never throw).
- Use `--enable-dry-run=true|false`, not bare `--check`.
- Run `tests/integration/test_runner_spe1.py` + `test_simulation_runner.py` (8 tests total).

### Before touching the builder
- Offline path (use_llm=False) must work end-to-end for CI.
- Generated decks are auto-linted; if lint fails, deck is None.
- Run `tests/integration/test_builder_roundtrip.py` (4 tests: depletion/injection lint + dry-run).
- Run `tests/integration/test_dataset_validation.py` builder scenarios (10 tests).

### Suggested next stage
**Stage 4 (postprocess to spec)** is highest leverage: the KPI/plot layer mostly works (verified on SPE1 family + builder scenarios), and closing the known gaps unlocks the FastAPI backend (Stage 5), which consumes exactly those functions. See `docs/conversations/05-postprocess.md` for spec.

## File Map (What Lives Where)

```
opm_ai/
├── settings.py              # pydantic-settings, .env loader
├── cli.py                   # Click CLI (not yet wired to builder/runner)
├── llm/
│   ├── client.py            # LLMClient, provider abstraction
│   └── prompts/             # Jinja2 templates for LLM calls
├── builder/
│   ├── builder.py           # build_deck() entry, orchestrator
│   ├── extract.py           # extract_reservoir_info() regex engine
│   ├── models.py            # ModelSpec, ReservoirDescription, DeckGenerationResult
│   ├── templates/base.j2    # main Jinja2 deck template
│   └── context.md           # builder design notes
├── linter/
│   ├── linter.py            # lint_deck() entry, orchestrator
│   ├── deck.py              # hand-rolled section splitter
│   ├── models.py            # LintIssue, LintResult
│   ├── rules/               # L001-L015 implementations
│   │   ├── registry.py      # run_all(deck) dispatcher
│   │   ├── general.py       # L001, L013, L014
│   │   ├── runspec.py       # L002, L015
│   │   ├── grid.py          # L003, L003b, L004, L011
│   │   ├── props.py         # L005, L012
│   │   └── schedule.py      # L006, L007, L008, L014, L015
│   ├── prompts/summarize.j2 # LLM summary template
│   └── context.md           # **READ THIS BEFORE TOUCHING LINTER**
├── runner/
│   ├── runner.py            # run_simulation() entry
│   ├── models.py            # SimulationResult, CrashReport
│   └── context.md           # runner design notes (to be written)
├── postprocess/
│   ├── summary.py           # read_summary() via resfo
│   ├── kpi.py               # extract_kpis() field totals
│   ├── plots.py             # plot_production() Plotly
│   └── resinsight_bridge.py # rips gRPC stub (Phase 2)
├── preprocess/              # NOT STARTED (Phase 2)
├── api/                     # NOT STARTED (Stage 5)
└── explainer/               # NOT STARTED (Phase 3)

tests/
├── unit/
│   ├── test_linter.py       # 3 positive tests
│   ├── test_linter_negative.py  # 11 negative tests
│   ├── test_runner_spe1.py  # SPE1CASE1 happy path
│   └── test_settings.py
└── integration/
    ├── test_builder_roundtrip.py     # 4 tests (lint + dry-run)
    ├── test_dataset_validation.py    # 19 tests (fixtures + scenarios)
    └── test_simulation_runner.py     # 7 tests (edge cases)

docs/
├── Instructions.txt         # product vision + user guide
├── OPM.md                   # OPM Flow operational reference (217 options)
├── PROGRESS_REPORT.md       # audit findings + simulation sweep results
├── conversations/
│   ├── 00-setup.md          # Stage 0 skeleton
│   ├── 01-runner.md         # Part 1 spec
│   ├── 02-linter.md         # Part 2 spec
│   ├── 03-builder.md        # Part 3 spec
│   ├── 04-preprocess.md     # Part 4 spec (not started)
│   ├── 05-postprocess.md    # Part 5 spec (partial)
│   └── STATUS.md            # stage-by-stage progress log
└── IMPLEMENTATION_PLAN.md   # 6-stage incremental plan

tests/fixtures/              # 133 .DATA decks from opm-tests
├── spe1/                    # SPE1 variants (25 decks)
├── spe3/, spe5/, spe9/
├── wconprod/                # WCONPROD family (13 decks)
├── mult/, pinch/
└── spe1_brine/
```

## Commands to Verify Everything Still Works

```bash
cd /home/parallels/opm-ai
source .venv/bin/activate
python -m pytest tests/unit tests/integration -v  # should show 66 passed
```

## Operational Notes

- Python: 3.12+
- Deps: pydantic, pydantic-settings, Jinja2, Click, loguru, resfo>=5.0, numpy, pandas, plotly
- OPM Flow: 2026.04 at `/usr/bin/flow`
- Env: Ubuntu 24.04 arm64, no CUDA (GPU accelerator modes fail)
- Git: main branch = `main`, current branch = `master` (will reconcile)

## For the Next Session

If you're asked to build the full working app:
1. **Stage 4**: Close postprocess gaps (see 05-postprocess.md + debt #1).
2. **Stage 5**: Implement FastAPI backend (`opm_ai/api/`) per 06-api-frontend.md (routes: /build, /lint, /run, /results, /chat).
3. **Stage 6**: React frontend (port 8555 per Instructions.txt) with chat UI.
4. **Stage 7**: Docker + docker-compose.yml packaging.
5. **Stage 8**: CI (GitHub Actions), README, deployment docs.

Use Sonnet for routine implementation/testing, Opus for architectural decisions.
