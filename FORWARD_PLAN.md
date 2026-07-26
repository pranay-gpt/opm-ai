# FORWARD PLAN - Reconciliation Against the Aim (Instructions.txt)

> **STATUS 2026-07-22: Stages A-F ALL DONE.** The aim is met: plain-English chat
> builds, lints, runs, visualises, and explains simulations; repo is public with
> green CI; Docker one-liner works. What remains is the "Planned capabilities"
> list near the end of this file (4 items) plus the debt register. Read
> CONTEXT.md for architecture and invariants before continuing work.

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
| Part 3 Builder — **LLM extraction** | **DONE (live-verified 2026-07-21: 3 hard descriptions extracted via Groq, unit conversion m3/day-to-bbl/day and bar-to-psia correct, all decks lint-passing)** | Stage B (2026-07-20): `LLMClient.extract_json` (JSON mode + repair retry), `extract_model_spec.j2` prompt, `extract_parameters_llm` with Pydantic validation, wired into `build_deck(use_llm=True)` with offline regex fallback; chat tool passes use_llm=True. Offline tests green; live Groq verification pending (orchestrator, post-merge). |
| Part 3 Builder — scenario templates | DONE (Stage D, 2026-07-21) | wag/gas_cap/co2/buildup/multilayer render distinct Flow-verified decks; DATES/TSTEP schedule events in ModelSpec + base.j2 |
| Part 4 Preprocess | DONE | correlations, PROPS renderers, validators, advisor (43 tests) |
| Part 5 Postprocess — KPIs/plots | DONE | resfo reading, KPI dict, Plotly |
| Part 5 — ResInsight bridge | DONE (Stage 15) | batch-CLI snapshots; API + chat tool; NOTE: host-only (needs live X display; packaged binary has no gRPC — see wiki/memory) |
| Part 6 Chat brain | DONE (Stage C, live-verified 2026-07-21) | 7-tool loop exercised live on Groq (build→lint→run→kpis→snapshots→explain); fixed null-field 400, missing assistant turn, history bloat 413, event-loop blocking, and done/multi-turn protocol; 5 deterministic ws tests |
| Part 6 Settings panel | DONE (Stage C, live-verified 2026-07-21) | POST/GET /api/settings sets in-memory provider/key overrides on the settings singleton (never persisted, never echoed); frontend panel calls it; per-connection LLMClient picks it up without restart. |
| Part 7 Explainer | DONE (BM25 deviation, documented) | explain/quiz/learning-report, offline fallbacks |
| Part 8 Docker/CI | DONE | verified in LXD dockerhost 2026-07-20, smoke 7/7 |
| "Useable by anyone using GitHub" | DONE (Stage F 2026-07-21) | public repo https://github.com/pranay-gpt/opm-ai (MIT, main default); CI green on GitHub-hosted runners |
| Frontend served | BUILD-ON-DEMAND | frontend/dist is gitignored and absent on host; Docker builds it in-stage (verified); local serving requires `npm ci && npm run build` (node 18 present; sourcemaps disabled 2026-07-22 to halve build memory - 2GB heap now suffices; stop uvicorn first on this 3GB host) |
| Frontend snapshots UI | DONE (Stage E 2026-07-21) | ResultsViewer 3D Snapshots tab consumes GET /api/results/{id}/snapshots; shows bridge error string when unavailable |
| Frontend UI overhaul | DONE (2026-07-22) | Router navigation fixed (NavLink, SPA deep-link fallback), theme system (dark/light/auto, CSS vars, Monaco+Plotly follow), chat tool_call protocol fix, POST /api/decks + Browse upload, WS lifecycle + persistence fixes from max-effort review; 7-agent Playwright matrix all-PASS; screenshots in docs/screenshots/ |

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
STATUS: DONE (live-verified 2026-07-21: 3 hard descriptions extracted via Groq, unit conversion m3/day-to-bbl/day and bar-to-psia correct, all decks lint-passing) (2026-07-20). Implemented: extract_json in
LLMClient, extract_model_spec.j2 prompt, extract_parameters_llm with offline
fallback in build_deck, chat tool_build_deck uses use_llm=True,
ModelSpec.schedule placeholder for Stage D. Suite 200 passed offline; the
live-Groq step below remains for the orchestrator (no .env in worktree).
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
STATUS: DONE (2026-07-21). Live chat loop verified end-to-end and hardened.
Implemented:
- Settings made real via the recommended mechanism: POST /api/settings
  (opm_ai/api/routes/settings.py) sets in-memory attribute overrides on the
  settings singleton (plain assignment; pydantic-settings v2 permits it since
  validate_assignment is off). Never persisted, keys never echoed. GET returns
  provider + active_provider + per-provider key booleans. Chat picks it up
  without restart because LLMClient() is constructed per connection and reads
  settings at __init__. Frontend SettingsPanel now GETs/POSTs the API; keys no
  longer stored in localStorage (component state only, cleared after save);
  inert NIM base-url input replaced with env-var note.
- Chat session race hardening: per-session asyncio.Lock via
  SessionStore.get_session_lock() (bounded LRU dict, same max_entries as the
  session dict); routes/chat.py wraps every session read-modify-write in
  `async with` and snapshots history for LLM calls outside the lock.
- Tests: tests/integration/test_api_settings.py (7 tests: override, no key
  leakage, fresh-LLMClient-targets-new-provider with monkeypatched groq SDK,
  clear/omit key semantics, 422 on bad provider, fixture restores singleton)
  and tests/integration/test_chat_session_concurrency.py (4 tests; verified
  the unlocked variant loses 25/50 updates, so the test is a real guard).
  Suite: 214 passed, 1 skipped.
- Live-exercised the WebSocket tool loop (2026-07-21) and fixed what broke:
  1. Groq rejects messages carrying explicit null tool_calls/tool_call_id
     (400): history is now serialized with model_dump(exclude_none=True).
  2. The assistant turn that requested tools was never appended to history
     (providers require it before tool-role messages): now recorded.
  3. Tool results stuffed full deck text + Plotly JSON into history and blew
     provider TPM limits (413) on the next turn: compact_tool_result() now
     stores a preview + lint verdict / KPIs only; the frontend still gets the
     full payload.
  4. tool_build_deck/tool_lint_deck/read_summary ran blocking work on the
     event loop, stalling websocket keepalives (1011 ping timeout): moved to
     run_in_executor.
  5. Protocol completion: server now emits {"type": "done"} at end of turn
     (the frontend handled 'done' but the server never sent it), supports
     multiple turns per connection with reconnect-replay detection, error
     events carry the 'message' field the frontend reads, and double-close
     on disconnect is guarded.
  Live transcript (Groq, one session: build_deck via LLM extraction ->
  lint -> run_simulation -> get_kpis -> export_snapshots -> explain_concept,
  all tools fired correctly) saved to docs/chat_live_transcript.json.
  Deterministic coverage of the full event protocol (tool_call ->
  tool_result -> token -> done, multi-turn on one connection, replay
  ignored, offline error shape, compaction bounds) in
  tests/integration/test_chat_ws_loop.py (5 tests) with a scripted fake
  client, so CI proves the loop without network. Free-tier provider limits
  (Groq 100k tokens/day, NIM 504 timeouts) are an ops constraint, not a
  code gap; runtime provider switching via POST /api/settings was exercised
  live during verification.
- Exit criteria met: transcript in docs/; settings change takes effect
  without restart (verified live: offline -> groq -> nim -> groq while the
  server ran); concurrent-session test green.

### Stage D — Scenario templates + DATES (Builder Phase 2 remainder)
STATUS: DONE (2026-07-21). ScheduleEvent consumed by base.j2 (actions then
DATES/TSTEP advance; tstep_days accepts float|list); empty schedule stays
byte-identical (md5-verified). ModelSpec grew EQUIL overrides (datum
depth/pressure, WOC, GOC) and pvdg_rows. Scenario defaults in extract.py:
WAG = water half-cycle then 7 alternating WCONINJE gas/water events at
calendar quarters via DATES; GAS_CAP = GOC at base of layer 1, datum at GOC
at bubble point (4014.7 psia), producer completed k 2..nz; CO2_EOR = gas
injector + denser/more-viscous injection-gas PVDG (black-oil subset);
BUILDUP = uniform 50 md, 4000 stb/d bottom-layer producer, 180 d drawdown,
WCONPROD STOP ORAT 0 then 0.25-8 d TSTEPs; MULTILAYER = 500/50/200 md
contrast with kv/kh 0.1. Ground truth: all 5 decks pass flow dry-run exit 0
AND complete real runs (~0.2 s each). Physics verified in tests: buildup
WBHP rises after shut-in (2629 -> 4344 psia), gas-cap FGOR climbs above
solution GOR 1.27, WAG injects both fluids over 731 days. Deck-text WAG
alternation asserted instead of the expensive recovery-bounds run. Suite:
221 passed, 1 skipped. Prototype note: DATES works fine after START in
these decks; the OPM.md "Problem with keyword DATES" caveat applies only to
the SKIPREST restart deck it was observed in. WELOPEN SHUT/STOP zeroes
reported WBHP in Flow 2026.04, so buildup uses WCONPROD STOP ORAT 0 which
keeps WBHP reported and rising.
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

### Stage E — Results UI completion (snapshots + field KPIs) ✅ DONE
- ResultsViewer: "3D Snapshots" section calling GET /api/results/{id}/snapshots,
  rendering returned PNGs, showing the bridge's error string when unavailable
  (e.g. inside Docker). Small, self-contained.
- Postprocess debt from CONTEXT.md: field-level KPI names (FOPT/FWPT/FGPT
  recovery, max watercut, breakthrough day), plot_production per-producer traces,
  watercut -0.0 sanitization.
- Exit criteria: browser shows plots + snapshots + KPIs for a fresh run.

### Stage F — Ship it (the unmet "useable by anyone using GitHub" clause)
STATUS: DONE (2026-07-21). Repo live at https://github.com/pranay-gpt/opm-ai
(public, MIT, default branch main). master renamed to main and pushed over
SSH (HTTPS push hit a ~3.6MB egress cap in this environment; large binary
fixtures forced the SSH route). CI's first real run caught a latent bug:
seven test files and the explainer KB source dirs hardcoded
/home/parallels/opm-ai absolute paths, which only ever passed on this
machine; fixed to repo-relative resolution (conftest fixtures + __file__),
verified by running the exact CI commands from a foreign CWD. CI now green
on GitHub-hosted runners (Backend Unit Tests + Frontend Build both success).
Original Stage F checklist:
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

### Planned capabilities from Instructions.txt not yet built (2026-07-22 review)

Identified by a full code review against the plan; each is UI/plumbing work on
top of finished backend pieces, none blocks the shipped v1.

1. Real 3D View tab (GUIDE 1/3, ResInsight visualization): the Results page
   3D View tab renders a placeholder. Options: embed static snapshot PNGs
   (already served by /api/results/{id}/snapshots) as the tab content, or a
   lightweight three.js grid viewer reading EGRID geometry. The separate
   3D Snapshots tab already works on hosts with a display.
2. LLM lint summary surfaced in UI (Part 2 headline): the backend returns
   lint_summary but no component renders it; DeckEditor fabricates
   "All checks passed" instead. Render the real field in LinterPanel and
   DeckEditor result panes, delete the fabricated string.
3. Correlation selection (Part 4, "Ask user option if multiple correlation
   available"): preprocess implements the correlation family but the fluid
   section hardcodes Standing. Add a correlation dropdown to the DeckBuilder
   fluid card and thread it through BuildRequest.fluid.
4. Fuzzy keyword suggestions in linter (Part 2, "WELSPCES -> did you mean
   WELSPECS?"): add difflib.get_close_matches against the known-keyword set
   in the unknown-keyword rule path; pure offline, no LLM needed.

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
