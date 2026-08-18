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

---

# Progress update: 2026-08-05

Scope: two pieces of follow-on work since the 2026-07-19 audit:

1. **Audit backlog #11** — three small audit findings deferred from the
   2026-07-19 pass were picked up and fixed: F2.6 (lint route crashed on
   non-DeckSpec input), F1.6 + F8.6 + F8.9 (frontend lifecycle and empty-state
   hygiene on ResultsViewer / ChatPanel). Three commits landed, all with
   tests.

2. **Deck upload feature** — adds a `POST /api/upload_deck` route and an
   `Upload` button on the Simulator page so users with the deck on their
   laptop can push it to the server along with the sibling `include/` folder
   in one multipart POST. The returned `deck_path` slots into the existing
   `/api/run` flow unchanged. The `Browse` button (server-side path picker)
   is unchanged; the two buttons are complementary tools, not replacements.

## Summary

| Item | Commit(s) | Tests added | Suite delta |
|---|---|---|---|
| Audit backlog #11 (F2.6, F1.6, F8.6, F8.9) | 2b453bf, da20014, d84db71 | 4 backend + 0 frontend (source-grep) | 502 → 506 backend |
| Deck upload backend | 6005274, 5cb3915 | 11 backend | 506 → 513 backend |
| Deck upload frontend | e7a7bbc | 1 source-grep | 6 → 7 frontend |
| Docs (this file, STATUS, 06-chat-and-api, plan) | 8fad1da | n/a | n/a |

Total: backend **513 passed / 3 skipped / 0 failed** (was 502). Frontend
**7 tests passed** (was 6). `tsc --noEmit` clean.

## Audit backlog #11 details

- **F2.6 (lint route crashes on non-DeckSpec input)**: The lint route used to
  crash when given an input shape other than the documented `LintRequest`,
  which surfaced as a 500 to the client. Now the route returns 200 with a
  structured `{passed: false, errors: [...]}` so the client renders the
  error rather than a stack trace.
- **F1.6 / F8.6 / F8.9 (frontend lifecycle and empty-state hygiene)**: A handful
  of useEffect-style lifecycle and empty-state nits on `ResultsViewer` and
  `ChatPanel` (e.g. empty-data early returns rendering nothing visible,
  useEffect dependencies that re-fired on every render). Each is pinned by a
  source-grep regression guard so the next person doesn't quietly regress
  them.

## Deck upload feature details

The full design decisions are in `docs/conversations/PLAN-upload-deck.md` and
the API surface update is in `docs/conversations/06-chat-and-api.md`
(section 3 + section 10 caveats + Risks). Highlights:

- **Wire format**: single `multipart/form-data` POST. Required `deck` part
  (.DATA file), optional `include` parts (one per include file, each with
  its relative path as the part filename).
- **Server-side path**: writes to `tempfile.mkdtemp(prefix="opm_ai_upload_")`
  under the system temp dir (inside `get_allowed_roots()`), returns the
  `.DATA`'s server-side path. The `/api/run` flow accepts it unchanged.
- **Multipart limits**: Starlette defaults (1 MB / part, 1000 files) would
  reject any non-trivial deck — model2 has 30-50 MB `.grdecl` files and a
  73 MB include/ tree across 1000+ files. Override at the route:
  `max_part_size=256 MB`, `max_files=5000`.
- **Path sanitisation**: `_safe_relpath` (regex on `[A-Za-z0-9_./-]`, no
  absolute, no `..`, no backslash) plus defence-in-depth `resolve()` check
  that the target stays inside the per-upload include/ dir. A malicious
  client cannot escape the upload dir.
- **pyproject**: gains `python-multipart>=0.0.9`. Was previously transitive
  via FastAPI but missing from declared deps, so a clean `uv install` would
  crash with `Form data requires "python-multipart" to be installed`.
- **Frontend**: `DeckUploader.tsx` modal with two `<input>`s — one
  `<input type="file" accept=".DATA">` for the deck, one
  `<input type="file" webkitdirectory directory multiple>` for the
  include/ folder. The `Upload` button sits next to `Browse` on the
  Simulator page. `fetchMultipart<T>` helper in `api/client.ts` does NOT
  set `Content-Type` (the browser sets it with the correct `boundary=`
  parameter; setting it manually either loses the boundary or sends a
  wrong one).
- **Caveat (documented, not a bug)**: `webkitdirectory` is Chromium-only.
  Firefox/Safari users get a plain multi-file picker for the include/ folder
  that doesn't preserve the layout; the deck upload alone still works on
  any browser.

## Status: 2026-08-05 (later same day, first commit pair) — build pipeline fix + production smoke

### Build pipeline fix

After committing the upload feature, `npm run build` started failing — two
pre-existing fragilities that an `tsBuildInfo` cache had been hiding:

- `src/**/*.test.ts` files reference `node:fs`, `node:path`,
  `node:assert/strict`, `process` but `@types/node` wasn't in devDependencies.
- `DeckUploader.tsx` and `SimulationRunner.tsx` imported `UploadResponse`
  from `src/api/client.ts`; the type actually lives in `src/types.ts`.
  `tsc --noEmit` missed this because `noUnusedLocals: false` and `api/client.ts`
  re-exports types via `import type`; `tsc -b` did not.

Fixed in commit `241702e`: correct the two import paths, exclude
`src/**/*.test.ts{,x,-helpers.ts}` from `tsconfig.app.json` (they have their
own esbuild pipeline via `npm test`), and add `@types/node` to devDependencies.

### Production smoke suite

Extended `scripts/smoke.sh` with a `[5b/8]` end-to-end check that POSTs a
multipart/form-data with a deck + include/ folder to `/api/upload_deck` and
asserts the response writes both at a returned server-side path. Step
counters updated from /7 to /8 throughout. Commit `9b7b70d`.

The previously running server (`pid 676060`, from the main checkout, bound to
`127.0.0.1`, no `/api/upload_deck`) was stopped and replaced with a uvicorn
from the worktree bound to `--host 0.0.0.0:8000` so the LAN IP is reachable.
Running server is now task id `b6jbkdcn2` in the worktree's process group.

**Production-suite pass at `http://10.211.55.5:8000` — 8/8 OK:**

```
[1/8] Health check                       OK
[2/8] Frontend load                      OK
[3/8] Build + Lint API                   OK
[4/8] Full pipeline: run -> poll -> results   OK
[5/8] Results KPI check                  OK (KPIs.days = 720.0)
[5b/8] Deck upload API                   OK (writes to /tmp/opm_ai_upload_*/)
[6/8] CLI lint check                     OK
[7/8] Frontend production build          OK (local)
All smoke tests PASSED
```

The new check [5b/8] is the wire contract the frontend DeckUploader modal
relies on. A curl call proves it works over the network, not just against
`TestClient` — which is what `tests/integration/test_api_upload_deck.py` covers.

## Status: 2026-08-05 (later same day, second commit pair) — make 0.0.0.0 the default

The earlier workaround (manually rebinding to `0.0.0.0` via a separate
uvicorn invocation) is now folded into `scripts/run.sh` itself so the local
dev server matches production out of the box:

- `scripts/run.sh` was hardcoded to `--host 127.0.0.1` while
  `docker/entrypoint.sh` already used `--host 0.0.0.0` (with an
  `API_HOST` override). Closing the gap: `scripts/run.sh` now binds
  `0.0.0.0` by default. Override with `OPM_HOST=127.0.0.1
  ./scripts/run.sh` for loopback-only mode (mirrors `API_HOST`).
- `08-deployment.md` design-decisions table gets row 3b explaining the
  choice and its tradeoff (anything on `0.0.0.0` is reachable to
  anyone on the LAN; flip the env var when that's a problem).
  Section 6 implementation-step 10 (smoke script) updated to reflect
  the `/8` count and the LAN-reachable `BASE_URL` pattern.

Verified both modes:

- Default: `OPM_VENV=/home/parallels/opm-ai/.venv ./scripts/run.sh` →
  binds `0.0.0.0:8000`; `localhost` and `10.211.55.5` both 200.
  `BASE_URL=http://10.211.55.5:8000 ./scripts/smoke.sh` 8/8 OK.
- Loopback-only: `OPM_VENV=... OPM_HOST=127.0.0.1 ./scripts/run.sh` →
  binds `127.0.0.1:8000`; LAN unreachable as designed.

Server is left running under task id `bvx44lx7g` with the new default.

### Remaining open follow-ups (not blocking)

- No reaper for `opm_ai_upload_*` mkdtemp dirs on partial upload. Acceptable
  for v1; periodic cleanup task would be a small follow-up.

## Status: 2026-08-05 (later same day, third commit pair) — branch squash + cleanup

Before this commit the repo had drifted to **11 local branches and 3 remote
branches**. The substantive dev work since `0402f67` ("Spec: cleanup and
performance pass") was sitting on `worktree-3d-viewer` — 50 commits ahead
of `main`, never merged. `main` was at `b233d85`, lagging by 50 commits.

Three actions, in order, with reversibility notes:

### 1. Squash-merge `worktree-3d-viewer` -> `main`

Commit `ff13487` on main: "feat: deck upload, audit backlog #1-#11, build/run
hardening". 119 files, +76409 / -795 lines collapsed to one shippable unit.
The full 50-commit forensic history is preserved on the `worktree-3d-viewer`
branch (now also pushed to origin as a backup).

The squash commit message organises the 50 underlying commits into named
groups (audit backlogs #1-#11, deck upload feature, frontend test infra,
build/run hardening, docs refresh, Stage B/C/D/E features). Anyone reading
`git log main` gets the project's actual story; anyone wanting the
session-by-session diary reads `git log worktree-3d-viewer`.

Smoke 8/8 pass on `main` post-merge. `git push origin main` was a clean
fast-forward (`b233d85 -> ff13487`).

### 2. Delete the 8 stale local branches + worktrees

- 4 `worktree-agent-*` branches (their content was already merged into
  `worktree-3d-viewer` via `Merge Stage B` / `Merge Stage E` commits — keeping
  them around was noise).
- 4 stale local-only branches (`worktree-brag-composition-fix`,
  `worktree-readme-fix-3d`, `worktree-readme-update`,
  `worktree-stage3-builder-linter`) all 5 commits behind `main` with no
  in-flight WIP.

### 3. Delete the 2 remote branches with no PR history

GitHub API check (`/repos/pranay-gpt/opm-ai/pulls?state=all&head=...`)
returned `[]` for both — no open or closed PRs ever referenced
`origin/worktree-readme-fix-3d` or `origin/worktree-readme-update`. Both
branches pointed at commits already on `main` (`48ecf2c` and `8544760`,
respectively). Deleted via `git push origin --delete`.

### Final state

- 2 local branches: `main`, `worktree-3d-viewer`
- 2 remote branches: `origin/main`, `origin/worktree-3d-viewer`
- 2 worktrees: `/home/parallels/opm-ai` (main), `/home/parallels/opm-ai/.claude/worktrees/3d-viewer` (3d-viewer)

### Convention going forward

Feature work happens on `worktree-3d-viewer` (or a freshly-spawned
`worktree-<feature>` for parallel work); when a batch is shippable,
squash-merge into `main`, push, and keep the dev branch around as the
working home. `scripts/run.sh` expects to run from inside a worktree,
which enforces the convention operationally.

### Reversibility

- Branch refs recoverable from reflog for ~90 days if any deleted work
  turns out to be needed.
- The squash commit `ff13487` is a single object on `main`; revert with
  `git revert ff13487` if needed (counter-commit, doesn't un-squash).
- The `origin/main` push is the only step that's irreversible on the
  remote side. It succeeded; `main` now reflects the project's actual state.

---

# Progress update: 2026-08-19

Scope: One-click auto-fix flow for the lint UI, plus the docs refresh
that records the v2 linter's current architecture.

## Summary

| Item | Commit(s) | Tests added | Suite delta |
|---|---|---|---|
| LinterAPI façade + executor + cache | 06f014c, c58d656, f0abd7b | ~30 facade tests | backend suite stable |
| LinterAPI callsite routing | 82c1449, 968e8d9, 83a430e | (covered by above) | backend suite stable |
| Apply-fix endpoint + frontend button | 2e3409b | 5 integration | 36 linter tests pass |
| Frontend `inFlightRef` drop | ff2df67 | source-grep | n/a |
| v2 fix-proposal test pin | 02499e8, 3a8e12b | 2 (perf + fuzz) | included above |
| Docs refresh (this file, 02-linter, STATUS, redesign log/tasks) | (this commit) | n/a | n/a |
| Merge to main (no-ff) | b985c57 | n/a | n/a |

Suite on `main` after the merge: backend tests pass (36 linter-related
incl. apply-fix); frontend `tsc --noEmit` clean.

## What changed for the user

A "Apply Fix" button appears next to each lint issue that the v2
engine can auto-fix (currently the common L1+v2 rules). Clicking it:

1. POSTs `{deck_path, rule_id, line, original_value, new_value}` to
   `/api/lint/apply-fix`.
2. Server re-runs the proposer (drift check). On drift → 409, deck
   untouched.
3. On match → server writes the patched deck atomically, returns
   `{deck_text, lint: LintResult}`. The UI replaces its state from
   the response — no second `/lint` round-trip.

## What changed for the codebase

- New endpoint: `opm_ai/api/routes/lint.py::apply_fix_endpoint` +
  Pydantic `ApplyFixRequest` / `ApplyFixResponse`.
- New frontend surfaces: `FixProposalView` + `api.applyFix` +
  per-issue button in `LinterPanel.tsx`.
- `opm_ai/linter/linter.py` — `lint_deck_func` renamed to
  `lint_deck_combined` to disambiguate from the package-level
  `lint_deck` (which stays L1-only).
- `opm_ai/linter/models.py` — `LintIssue.fix_proposal` field
  (optional, typed via `FixProposal`).

## Architectural notes

- The apply-fix route is a **server-side re-proposer**, not a
  "trust the client" endpoint. The client supplies its view of
  `original_value`, but the server re-runs `propose_fix` and only
  writes if both sides agree. This keeps the route handler to ~80
  lines of validation + write, with no string-replace logic that
  could diverge from the rule engine's view.
- `LintIssue.fix_proposal` is now the **stable contract** between
  the deterministic rule engine and the future LangChain agent's
  tool surface. Whatever the agent returns (its own proposal or an
  LLM-freetext rewrite) must conform to
  `{rule_id, line, original_value, new_value}` for
  `/api/lint/apply-fix` to consume it. Pinning this here means
  adding a new proposal source later does not touch the route
  handler.

## Why the merge branch was renamed from `linter-redesign`

The branch was created as `linter-redesign` for the v2 work
(LINTER_REDESIGN_LOG). The LinterAPI façade, the executor, the cache,
and the apply-fix endpoint were all developed against that branch's
goals. The branch was renamed to `feat/linter-as-tool` mid-stream
because the apply-fix cut is no longer pure refactor — it adds new
API surface (a route, a frontend button, a Pydantic model pair).
The redesign log/plan still own the rationale; the branch name now
honestly describes the cut's shape.

