# Finalization Checklist (2026-07-18)

This checklist documents the finalization work completed before Stage 0.5 implementation begins.

## Documentation Complete

- [x] `STATUS.md` written - living resume with verified state, defects, decisions, drift table
- [x] `IMPLEMENTATION_PLAN.md` updated - Stage 0.5 inserted, "rewrite v1 clean" decision captured
- [x] `00-overview-and-architecture.md` - SUPERSEDED note added pointing to STATUS.md
- [x] `README.md` - START HERE section added with STATUS.md as primary entry
- [x] All 9 design docs (00-08) authored and cross-consistent
- [x] Non-ASCII cleaned from IMPLEMENTATION_PLAN.md (§ -> section, em-dash -> hyphen)
- [x] Total: 2813 lines of finalized planning docs

## Tasks Created for Stage 0.5

- [x] Task #5: Reconcile pyproject.toml dependencies (drop streamlit, add click/fastapi/uvicorn)
- [x] Task #6: Fix pytest.ini config and register markers
- [x] Task #7: Reconcile .env.example and settings.py keys
- [x] Task #8: Add negative/round-trip tests (xfail until modules rewritten)
- [x] Task #9: Initialize git and make first commit

## Verified Facts (grounded in code/filesystem, not aspirations)

- [x] OPM Flow 2026.04 at `/usr/bin/flow` (confirmed via `flow --version`)
- [x] SPE1 simulation runs in ~0.48s (300-cell black-oil model)
- [x] Venv has `include-system-site-packages = false` - system opm/resfo/rips NOT visible
- [x] `opm_ai/` contains v1 sketch (~2036 lines) - all 33 tests pass
- [x] Known defects: stray docstring in base.j2, linter has no severity model
- [x] Git not initialized (`.git/` exists but empty)
- [x] `opm-ai` console script not installed (need `pip install -e .` after pyproject fix)

## Ready to Build

The plan is finalized, verified, and durable. After `/compact`, Stage 0.5 tasks (#5-9) can proceed in order.
