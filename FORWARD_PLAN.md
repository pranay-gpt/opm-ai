# FORWARD PLAN — Reconciliation Against the Aim (Instructions.txt)

Written 2026-07-20 after Stage 15 (ResInsight bridge). This document reconciles what
is built against the stated aim and defines the path to "finished". It supersedes
the stage list in IMPLEMENTATION_PLAN.md (all original stages are closed; this is
the continuation plan). Read CONTEXT.md first for architecture and invariants.

## The Aim (verbatim core, from Instructions.txt GUIDE 3)

> "To create an AI layer on top of open source reservoir simulators that will help
> academic students, researchers and faculty to understand and teach reservoir
> simulation in the most efficient and fun way using simple chats. There will be
> pre and post processing layers/workflow. It should be open source and useable by
> anyone using GitHub."

Definition of done implied by the aim: a student types plain English in a chat,
the system builds a deck (LLM-assisted), lints it, runs OPM Flow, shows visual
results (plots + 3D), and explains them educationally — all via
`git clone && docker compose up`, open source on GitHub.

## Reconciliation: aim vs built (honest scorecard, verified 2026-07-20)

| Aim component (GUIDE 1/3) | State | Evidence / gap |
|---|---|---|
| Part 1 Runner | DONE | never-raise contract, crash parsing, 8 integration tests |
| Part 2 Linter | DONE | L001-L015, calibrated FP=0 over 133 decks |
| Part 3 Builder — offline path | DONE | 8 scenarios, FIELD+METRIC, auto-lint |
| Part 3 Builder — **LLM extraction** | **STUB** | `build_deck(use_llm=True)` silently falls back to regex (builder.py `TODO: Phase 2`). No extraction prompt, no `extract_json` in LLMClient. This is the headline promise of the aim ("AI layer", "LLM Extraction: Uses Groq to parse description"). |
| Part 3 Builder — scenario templates | PARTIAL | wag/gas_cap/co2/buildup/multilayer render as depletion-like decks; no DATES schedules |
| Part 4 Preprocess | DONE | correlations, PROPS renderers, validators, advisor (43 tests) |
| Part 5 Postprocess — KPIs/plots | DONE | resfo reading, KPI dict, Plotly |
| Part 5 — ResInsight bridge | DONE (Stage 15) | batch-CLI snapshots; API + chat tool; NOTE: host-only (needs live X display; packaged binary has no gRPC — see wiki/memory) |
| Part 6 Chat brain | DONE code-path, **UNVERIFIED live** | real tool-calling loop wired for 7 tools, but `LLM_PROVIDER` unset → offline; never exercised against live Groq |
| Part 6 Settings panel | **COSMETIC** | frontend stores provider+keys in localStorage but never sends them to the backend; `LLMClient()` reads only server env. Settings UI has no effect on chat. |
| Part 7 Explainer | DONE (BM25 deviation, documented) | explain/quiz/learning-report, offline fallbacks |
| Part 8 Docker/CI | DONE | verified in LXD dockerhost 2026-07-20, smoke 7/7 |
| "Useable by anyone using GitHub" | **NOT DONE** | no git remote configured; never pushed. README quickstart URL is aspirational. |
| Frontend served | BUILD-ON-DEMAND | frontend/dist is gitignored and absent on host; Docker builds it in-stage (verified); local serving requires `npm ci && npm run build` (node 18 present; NODE_OPTIONS=--max-old-space-size=4096 needed for plotly) |
| Frontend snapshots UI | MISSING | new GET /results/{id}/snapshots endpoints have no UI consumer yet |

Test suite: 189 passed after fixing one CWD-dependent test
(test_path_traversal_relative_outside_rejected asserted 400 for a path that
legitimately resolves into the allowlisted /tmp when run from the repo root; now
probes $HOME instead).

## Verification protocol ("make sure whatever is built is 100% working")

Before each stage below, and as Stage A in full:

1. `source .venv/bin/activate && python -m pytest tests/unit tests/integration -q`
   → must be green from the REPO ROOT (CWD-dependence is a defect; the one known
   case is fixed).
2. Live server pass (not TestClient): `uvicorn opm_ai.api.server:create_app
   --factory --port 8000`, then `BASE_URL=http://localhost:8000 ./scripts/smoke.sh`
   → 7/7.
3. Browser-level pass once dist exists: build → lint → run → results → explain
   → snapshot, through the real UI. (Playwright MCP or manual.)
4. Docker pass (LXD dockerhost) once per release-candidate: compose up --build,
   in-container smoke.

## Forward stages (do in order; each is one committable increment)

### Stage A — Ground truth + local serving (small, do first)
- Run the verification protocol steps 1-2 as-is; fix anything red.
- Build the frontend locally: `cd frontend && npm ci &&
  NODE_OPTIONS=--max-old-space-size=4096 npm run build`; confirm the API serves
  the SPA at / and every page loads against the live backend.
- Exit criteria: suite green from repo root; smoke 7/7 on live server; SPA served.

### Stage B — LLM extraction end-to-end (the aim's headline; highest priority)
- `LLMClient.extract_json(prompt, schema) -> dict | None`: provider-agnostic
  structured output (Groq/OpenAI JSON mode where available, else strict-prompt +
  parse + one repair retry). Never raises; None on failure.
- `opm_ai/llm/prompts/extract_model_spec.j2`: system+user template embedding the
  ModelSpec JSON schema and 3-5 few-shot examples (use the 8 scenario docstrings).
- `extract_parameters_llm(desc) -> ModelSpec | None` in builder/extract.py:
  call LLM, validate via Pydantic, on any failure fall back to
  extract_parameters_offline (aim GUIDE 1: offline regex stays the deterministic
  safety net; CI stays offline).
- Wire into build_deck use_llm=True branch (replace the TODO).
- Set LLM_PROVIDER=groq in .env (keys already present). Live-verify once with a
  real Groq call on 3 descriptions an offline regex cannot parse (e.g. "a quarter
  five-spot with 160-acre spacing", "inject water at 1000 m3/day METRIC").
- Tests: offline-mocked unit tests (fake client returning canned JSON: valid,
  invalid-schema, garbage) + one skipif-no-key live integration test.
- Exit criteria: `build_deck(desc, use_llm=True)` produces a lint-passing deck
  from a description the regex path cannot handle; suite green offline.

### Stage C — Chat brain verified live + Settings made real
- Live-exercise the WebSocket tool loop with LLM_PROVIDER=groq: one session doing
  build → run → kpis → explain → export_snapshots. Fix what breaks (tool-call JSON
  quirks, session state).
- Make Settings real, pick ONE mechanism and document it: recommended = POST
  /api/settings that sets provider/key for the process (in-memory override on
  Settings, never persisted to disk), chat reads it; frontend Settings panel calls
  it. Alternative if rejected: delete the cosmetic key fields and document
  server-env-only config. Cosmetic-but-inert UI is worse than either.
- Chat session race hardening (known gap): per-session asyncio.Lock around
  session read-modify-write in routes/chat.py; test with two concurrent
  connections on one session id.
- Exit criteria: live chat demo transcript saved to docs/; settings change takes
  effect without restart; concurrent-session test green.

### Stage D — Scenario templates + DATES (Builder Phase 2 remainder)
- WAG: alternating WCONINJE water/gas cycles (needs DATES or TSTEP blocks per
  half-cycle). Gas-cap: EQUIL with gas-oil contact above datum + initial Sg.
  CO2: gas injector with CO2-ish PVDG and stream comment (stay in black-oil
  subset per GUIDE 2 - no compositional keywords). Buildup: producer flow period
  then shut-in (WELOPEN) with short TSTEPs. Multilayer: per-layer PERMX contrast.
- DATES schedule support in ModelSpec + base.j2 (calendar dates instead of bare
  TSTEP), since WAG/buildup need it anyway.
- Ground truth every new template: flow dry-run exit 0 AND a short real run;
  extend test_dataset_validation.py scenario sweep.
- Physics sanity per aim (educational correctness): WAG recovery between
  waterflood and depletion bounds; buildup BHP rises during shut-in; gas-cap GOR
  rises early. Assert loosely in tests.
- Exit criteria: all 8 scenarios render distinct, physically sensible decks that
  run in Flow; suite green.

### Stage E — Results UI completion (snapshots + field KPIs)
- ResultsViewer: "3D Snapshots" section calling GET /api/results/{id}/snapshots,
  rendering returned PNGs, showing the bridge's error string when unavailable
  (e.g. inside Docker). Small, self-contained.
- Postprocess debt from CONTEXT.md: field-level KPI names (FOPT/FWPT/FGPT
  recovery, max watercut, breakthrough day), plot_production per-producer traces,
  watercut -0.0 sanitization.
- Exit criteria: browser shows plots + snapshots + KPIs for a fresh run.

### Stage F — Ship it (the unmet "useable by anyone using GitHub" clause)
- Create GitHub repo, add remote, reconcile master→main (CONTEXT.md notes this),
  push. Verify CI workflows actually run green on GitHub (they have never run).
- README truth pass: real clone URL, real quickstart, troubleshooting section
  (OPM crash messages + the ResInsight no-gRPC/display caveat), demo GIF of
  chat → deck → run → results.
- Docker: decide on snapshots-in-container (add xvfb + Mesa software GL to the
  image and set QT_QPA_PLATFORM accordingly, or document host-only). Re-verify
  compose in dockerhost either way.
- Exit criteria: fresh `git clone && docker compose up` on a clean machine path
  works; README demo matches reality.

### Deferred (post-ship, keep in debt register)
- Linter deep-parse mode for the 9 FN classes; INCLUDE resolution;
  GCONPROD/VFP/ACTIONX rules.
- Explainer vector-backend upgrade (documented in explainer/context.md).
- NOECHO/ECHO template cleanup + PVTO monotonicity warning.
- Norne/SPE9-class showcase deck in docs (GUIDE 2 test philosophy).

## Ordering rationale

B before C: chat's build_deck tool inherits LLM extraction for free once B lands.
D after B: LLM extraction should emit the new scenario fields, so define them in
D with B's schema in mind (add optional ModelSpec fields in B, implement
templates in D). E anytime after A; it is independent. F last because every
earlier stage changes what the README must claim.

## Session notes for the next chat (Fable 5)

- Verify before claiming: every stage ends with the verification protocol, and
  live-LLM claims need a real transcript, not a code-path argument.
- LLM_PROVIDER default stays "offline"; only .env opts in (linter latency
  invariant, CONTEXT.md).
- Never weaken the linter calibration gate or the runner never-raise contract.
- Use worktrees for isolation (repo settings set baseRef=head; master is the
  working branch until F reconciles main).
- Known env facts: node 18 + npm 9 on host; ResInsight snapshots need DISPLAY=:0
  (memory: resinsight-no-grpc); dockerhost LXD container runs docker.
