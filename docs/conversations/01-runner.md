# Part 1: OPM Flow engine wrapper  (module: opm_ai.runner)

> Turn a validated deck into a structured, never-raising SimulationResult by driving `/usr/bin/flow` and locating its output files.

## 1. Role in the AIM

- The runner is the physics executor: the point where "chat -> deck" becomes an
  actual reservoir simulation. Everything upstream (builder, linter) produces a
  deck; everything downstream (postprocess, explainer, UI) consumes results.
- Educational value depends on runs being reliable and legible. A student typing
  plain English must never see a Python stack trace. Failures must come back as a
  readable CrashReport (which keyword, which line, what went wrong), not an
  exception. That "never raise, always explain" property is the whole reason this
  module exists as a wrapper rather than a raw `subprocess.run` call at the callsite.
- It is the first module built (Stage 1) because it proves the installed toolchain
  works end to end before any AI layer is added.

## 2. Position in build order

| | |
|---|---|
| Phase | Phase 1 (v1), Stage 1, immediately after Stage 0 skeleton |
| Depends on | Stage 0 (`opm_ai` package, `settings.py` exposing `OPM_FLOW_BINARY`); a deck file on disk; `/usr/bin/flow` installed |
| Depended on by | Part 5 postprocess (`read_summary`/`extract_kpis` consume `result.output_dir`), the CLI `run` command, the FastAPI `/api/run` route (Stage 5) |
| Does NOT depend on | linter, builder, LLM. The runner runs any `.DATA` path it is given. Validation is the linter's job (see 02-linter.md); the runner only reports what flow itself rejects. |

Cross-links: see 00-overview-and-architecture.md, 02-linter.md, 05-postprocess.md.

## 3. Hard API contract

Asserted by `tests/integration/test_runner_spe1.py` and specified in
BUILD_GUIDE.md section 4.

```python
# opm_ai/runner/models.py
SimulationJob(deck_path: Path, output_dir: Path, timeout: int)   # kwargs, per test

# opm_ai/runner/runner.py
def run_simulation(job: SimulationJob) -> SimulationResult: ...

# SimulationResult (attributes the test reads)
result.success: bool          # True on a clean flow exit
result.crash_report           # CrashReport | None; str(...) must be readable
result.output_dir: Path       # exists() after a successful run

# CrashReport (BUILD_GUIDE.md section 4)
CrashReport(keyword: str | None, line: int | None, message: str)
```

Exact assertions in `test_runner_spe1.py` (marked `integration`, `slow`):

```python
job = SimulationJob(deck_path=fixture_path,
                    output_dir=tmp_path / "spe1_output", timeout=120)
result = run_simulation(job)
assert result.success, f"Flow failed: {result.crash_report}"
assert result.output_dir is not None
assert result.output_dir.exists()
# then read_summary(result.output_dir) and extract_kpis(...) are called (Part 5)
```

Hard rules distilled:
- `run_simulation` MUST NOT raise for any input. Bad path, nonzero exit, timeout,
  missing binary all return a `SimulationResult(success=False, crash_report=...)`.
- `result.crash_report` must render usefully in an f-string (drives the assert
  message and, later, the chat explanation).
- `output_dir` is the caller-chosen directory, distinct from the deck directory
  (the fixture ships precomputed outputs; writing into `tmp_path` keeps them clean).

## 4. Key design decisions

### 4.1 subprocess to /usr/bin/flow (primary) vs opm.simulators.BlackOilSimulator

- Decision: drive the CLI binary `/usr/bin/flow` via `subprocess`. The Python
  binding is a documented future path, not v1.
- Rationale:
  - Simpler and matches IMPLEMENTATION_PLAN Stage 1 wording ("subprocess to
    `/usr/bin/flow`").
  - Honours `--output-dir` natively (OPM.md 2, 3.2), so file discovery is a glob
    of one directory.
  - Crash isolation: a segfault or `SIGABRT` (exit 134, OPM.md 7.8 pitfall 4)
    kills a child process, not the FastAPI/CLI parent. An in-process binding would
    take the server down with it.
  - Physics auto-detection: one binary handles black-oil, gas-water, thermal,
    CO2STORE from deck keywords (OPM.md 1). No need to pick a binding class
    (`BlackOil` vs `GasWater` vs `OnePhase`) per deck.
  - Timeout and cancellation are trivial with `subprocess.run(timeout=...)`;
    in-process runs cannot be time-boxed cleanly.
- Alternatives considered:
  - `opm.simulators.BlackOilSimulator` (present at
    `/usr/lib/python3/dist-packages/opm/simulators`). Needed later for MPI control,
    PYACTION callbacks, and step-by-step SummaryState introspection. Its exact
    constructor/step API is UNVERIFIED here; do not build against it until Part 4/7
    require it. Keep the runner interface (`SimulationJob` -> `SimulationResult`)
    stable so a binding backend can be swapped in behind it.
  - `mpirun -np N flow ...` for parallel. Deferred: SPE1 is 300 cells and runs
    serially in ~0.5 s (OPM.md 7.3). Parallel adds the `nproc`/`--oversubscribe`
    constraint (OPM.md 7.4) and changes the INIT keyword set. Not needed for v1.
- Consequences: the wrapper is a process manager plus a log parser. No new runtime
  dependency (uses stdlib `subprocess`, `pathlib`, plus `loguru`/`pydantic` already
  in `pyproject.toml`).

### 4.2 Exact command template

- Decision (serial v1):

```bash
flow --output-dir=<output_dir> <deck_path>
```

  Built as an argv list (no shell):
  `[flow_binary, f"--output-dir={output_dir}", str(deck_path)]`.
- OMIT any thread flag. Rationale: GUIDE 1 / BUILD_GUIDE say to omit `--threads`
  due to compatibility issues. The older Instructions.txt uses
  `--enable-num-threads`, which is NOT in the flow 2026.04 catalog (OPM.md 3.8 lists
  only `--threads-per-process`, default 2). Passing an unknown option makes flow
  abort (OPM.md 1). Omitting the flag entirely lets flow use its default and avoids
  the trap. Revisit `--threads-per-process` only for a deliberate performance mode.
- Deck path: pass an absolute path; flow resolves `INCLUDE` relative to the deck's
  directory. SPE1CASE1 is self-contained, but general decks are not, so do not copy
  the deck away from its includes. Keep `output_dir` separate from the deck dir.
- Output dir: `mkdir -p` it before launching (OPM.md 9: "not always auto-created
  cleanly across versions").
- Booleans, if ever added, need explicit `true`/`false` (OPM.md 1). Leave binary
  ECL output and ESMRY at their defaults (`--enable-ecl-output=true`,
  `--enable-esmry=true`, OPM.md 3.2) so `.SMSPEC/.UNSMRY/.ESMRY` are written for Part 5.
- Invocation:

```python
proc = subprocess.run(argv, cwd=deck_path.parent, capture_output=True,
                      text=True, timeout=job.timeout, start_new_session=True)
```

  `start_new_session=True` puts flow in its own process group so a timeout kill can
  reap the whole group (future-proofs the eventual `mpirun` path).

### 4.3 Exit code and timeout handling

Ground truth: OPM.md 9 ("Exit codes / output parsing").

| Condition | Detection | Result |
|---|---|---|
| Success | `returncode == 0` | `success=True`, `crash_report=None` |
| Handled error | `returncode == 1` | `success=False`, parse PRT/stderr for `Error:` |
| Internal assertion / core dump | `returncode == 134` (SIGABRT) | `success=False`, message "flow aborted (assertion/core dump)" plus parsed line |
| Timeout | `subprocess.TimeoutExpired` | `success=False`, `crash_report=CrashReport(None, None, f"timed out after {timeout}s")`, kill process group |
| Binary missing | `FileNotFoundError` on the binary | `success=False`, message names the missing `OPM_FLOW_BINARY` path |
| Any other exception | broad `except Exception` | `success=False`, message = repr; never propagate |

- `returncode` is captured on the result for debugging.
- Do NOT treat stderr text alone as failure: several companion tools and flow
  itself print informational text to stderr (OPM.md 8.4). Gate on exit code first.

### 4.4 Crash and warning parsing

- Primary source: `<output_dir>/<CASE>.PRT` (human-readable). Secondary:
  `<CASE>.DBG` (verbose) and captured stderr. OPM.md 1, 9: real diagnostics live in
  the PRT/DBG, not necessarily on stdout.
- CrashReport population:
  - `message`: the last non-stack-trace line containing `Error:` or
    `Simulation aborted` (OPM.md 9). Fall back to the final stderr line.
  - `keyword`: extracted when the message names one, e.g.
    `Problem with keyword DATES`, `Problem with keyword RESTART` (OPM.md 7.12).
    Regex on `keyword ([A-Z0-9]+)`; else `None`.
  - `line`: parsed from OPM parser diagnostics that carry a deck line reference
    (`opmi` lists keywords "with line refs", OPM.md 8.6). If none present, `None`.
- Fatal vs warning classification:

| Class | Signal | Action |
|---|---|---|
| Fatal | exit != 0, or `Error:` / `Simulation aborted` in PRT | `success=False` + CrashReport |
| Warning | exit == 0 with `Warning:` lines in PRT | `success=True`; collect into `result.warnings: list[str]` (non-contract extra) |
| Benign | stderr info text, `Simulation turned off` (dry-run) | ignored |

- Known real error strings to recognize (from OPM.md 7):
  - `cusparseSolver was chosen, but CUDA was not found` (7.6): GPU unavailable.
    Only relevant if the wrapper ever sets `--accelerator-mode`; v1 does not.
  - `Error locating serialized restart file` (7.8): restart misuse; out of scope
    for v1 (no restart in the runner yet).
  - `The restart file ... does not exist` / `Problem with keyword RESTART` (7.12):
    surfaces if a builder-generated restart deck is run later.
  - Parse-time `Internal error: Tried to get uninitialized value from DeckItem`
    (7.12): usually a malformed keyword record; report verbatim.

### 4.5 Output file discovery

Verified SPE1 output set (`tests/fixtures/spe1/`, and a fresh run per OPM.md 7.3):
`CASE.{DBG,EGRID,ESMRY,INIT,PRT,SMSPEC,UNRST,UNSMRY}`. Note: no `.OPMRST` unless
`--save-step` is used; no `.FUNRST` unless `convertECL` is run.

- Base name = deck stem (`deck_path.stem`, e.g. `SPE1CASE1`). flow names all
  outputs `CASE.*` regardless of `--output-dir`.
- Discovery: glob `output_dir` for the expected extensions and attach a mapping on
  the result (non-contract but used by Part 5):

| Ext | Meaning | Consumer |
|---|---|---|
| `.SMSPEC` + `.UNSMRY` | classic summary spec + data | `read_summary` (resfo) |
| `.ESMRY` | fast unified summary | `read_summary` (preferred; resfo >=5.0) |
| `.UNRST` | unified restart (cell states over time) | ResInsight / 3D (Part 5) |
| `.EGRID` | grid geometry | ResInsight / 3D (Part 5) |
| `.INIT` | static init props | ResInsight |
| `.PRT` / `.DBG` | diagnostics | crash parsing (this module) |

- `read_summary` (Part 5) can read either `.ESMRY` or `.SMSPEC/.UNSMRY`; the runner
  only guarantees they exist. It does not parse binary output itself.

### 4.6 Which summary vectors matter educationally

Critical fact: available vectors are exactly what the deck's `SUMMARY` section
requests. SPE1CASE1's SUMMARY (verified, lines 282-367) requests
`FOPR, FGOR, WBHP:{INJ,PROD}, WOPR:{INJ,PROD}, WOPT:{INJ,PROD}` and more. The test
asserts `WOPT:PROD` exists because the deck asks for it.

Educational shortlist (feeds 05-postprocess.md; not all present in every deck):

| Vector | Meaning | In SPE1 SUMMARY |
|---|---|---|
| WOPR:<well> | well oil production rate | yes |
| WOPT:<well> | well cumulative oil | yes (test target) |
| WBHP:<well> | well bottom-hole pressure | yes |
| FOPR | field oil production rate | yes |
| FGOR | field gas-oil ratio | yes |
| WWCT:<well> | well water cut | no (gas-injection case) |
| FOPT | field cumulative oil | no (not requested) |
| FPR | field average pressure | no (not requested) |

- Consequence for Part 5: KPI extraction must be defensive. `extract_kpis` returns
  `days` (always derivable from `TIME`) plus whichever field/well KPIs are present,
  hence the test's `assert len(kpis) > 1` rather than a fixed set.
- Optional future aid: to guarantee a rich educational set regardless of the input
  deck, a builder-generated deck can be given a standard SUMMARY block. The runner
  itself must not mutate a user's deck.

## 5. Toolchain grounding

| Item | Value | Source / status |
|---|---|---|
| Binary | `/usr/bin/flow` | verified `flow --version` -> `flow 2026.04` |
| Flow version | 2026.04 (Ubuntu 24.04, Open MPI 4.1.6) | OPM.md header, verified |
| Binary path config | `settings.OPM_FLOW_BINARY`, default `/usr/bin/flow` | Stage 0 `settings.py` (IMPLEMENTATION_PLAN Stage 0) |
| Command form | `flow --output-dir=OUT DECK.DATA` | OPM.md 2, 6, 7.3 verified (exit 0, ~0.5 s) |
| Dry-run validate (optional) | `flow --enable-dry-run=true --output-dir=OUT DECK.DATA` | OPM.md 7.2 verified |
| Thread flag | OMIT | GUIDE 1 / BUILD_GUIDE; `--enable-num-threads` is UNVERIFIED (not in 2026.04 catalog) |
| Diagnostics | `CASE.PRT`, `CASE.DBG` in `--output-dir` | OPM.md 1, 9 |
| Python binding (future) | `opm.simulators.BlackOilSimulator` at `/usr/lib/python3/dist-packages/opm/simulators` | path exists; exact API UNVERIFIED, do not code against yet |
| Runtime deps for this module | `subprocess`,`pathlib` (stdlib); `pydantic`,`loguru` (already in pyproject) | no new dependency |

UNVERIFIED / to check at implementation time:
- Does flow 2026.04 return exactly `1` for a deck error vs `134` for asserts across
  the deck families we care about? Confirm by running a deliberately broken deck.
- `BlackOilSimulator` constructor and stepping API: read the binding before Part 4/7.
- Whether `subprocess` timeout reliably reaps flow's async ECL output thread; verify
  with a short timeout on a long deck.

## 6. Implementation approach

Files to create under `opm_ai/runner/`:

1. `__init__.py` - export `run_simulation`, `SimulationJob`, `SimulationResult`,
   `CrashReport`.
2. `models.py`:
   - `CrashReport` (pydantic BaseModel): `keyword: str | None = None`,
     `line: int | None = None`, `message: str`. Define `__str__` for the f-string.
   - `SimulationJob` (pydantic BaseModel): `deck_path: Path`, `output_dir: Path`,
     `timeout: int = 300`. Accept kwargs exactly as the test passes them.
   - `SimulationResult` (pydantic BaseModel): contract fields `success: bool`,
     `crash_report: CrashReport | None`, `output_dir: Path`; extras
     `return_code: int | None`, `timed_out: bool = False`, `duration_s: float`,
     `stdout: str`, `stderr: str`, `warnings: list[str] = []`,
     `summary_files: dict[str, Path] = {}`, `prt_path: Path | None`.
3. `runner.py`:
   1. Resolve `flow_binary` from settings; if not executable, return a failed result.
   2. `output_dir.mkdir(parents=True, exist_ok=True)`.
   3. Build argv `[flow, f"--output-dir={output_dir}", str(deck_path)]`.
   4. `subprocess.run(..., capture_output=True, text=True, timeout=job.timeout,
      cwd=deck_path.parent, start_new_session=True)` inside try/except.
   5. On `TimeoutExpired`: kill the process group, build timeout CrashReport.
   6. On success (rc 0): discover output files, collect warnings, return
      `success=True`.
   7. On nonzero rc: parse PRT then stderr into a CrashReport, return
      `success=False`.
   8. Wrap the whole body so no exception escapes.
4. `_parse.py` (or private helpers in `runner.py`): `parse_prt(path) ->
   (CrashReport | None, warnings)`, `discover_outputs(output_dir, stem) -> dict`.
5. `context.md` - per CLAUDE.md folder rule: purpose, contract, decisions summary.

Order of work (TDD): write `models.py`, then a minimal `runner.py` that runs SPE1
and returns `success` + `output_dir` (enough for the first two asserts), then add
PRT parsing and failure paths. The full `test_runner_spe1.py` also imports
`read_summary`/`extract_kpis` (Part 5), so it goes fully green only after Stage 4;
until then, prove the runner with a focused assertion or a temporary test that
stops before the summary read.

## 7. Risks and open questions

- The gating test couples runner and postprocess: `test_runner_spe1.py` imports
  `opm_ai.postprocess.summary` and `opm_ai.postprocess.kpi` at module top. It will
  error on collection until those modules exist. Decision needed: build a stub
  `postprocess` in Stage 1, or gate/skip this test until Stage 4 (IMPLEMENTATION_PLAN
  Stage 1 flags this). Recommend a thin stub or an `importorskip` so Stage 1 has a
  runnable proof.
- Dependency gaps (not this module, but flagged): `pyproject.toml` still lists
  `streamlit` and omits `click`/`fastapi`/`uvicorn` that later tests import; `resfo`,
  `loguru`, `pydantic`, `pandas`, `plotly`, `rips` are present. Runner needs none of
  the missing ones. See 00-overview-and-architecture.md for the cleanup.
- Exit-code semantics may vary by deck family; the 0/1/134 mapping is verified only
  for SPE1-class runs. Keep the classifier data-driven (search for message strings),
  not purely code-number based.
- Long educational decks (SPE10, Norne) can exceed a short default timeout. `timeout`
  is caller-supplied; the CLI/API should expose it with a sane default and surface a
  clear timeout CrashReport rather than a silent hang.
- Concurrency: multiple runs must use distinct `output_dir`s (flow clears/writes the
  dir). The API layer (Stage 5) owns per-job directories; the runner assumes the
  caller gives it a clean, unique dir.
- `--output-dir` clobbering: never point `output_dir` at a fixture directory; it
  would overwrite the shipped reference outputs.

## 8. Verification and done-criteria

- Gating test: `tests/integration/test_runner_spe1.py` (markers `integration`,
  `slow`; requires OPM Flow installed).
- Prove Stage-1 completion:
  1. `pytest tests/integration/test_runner_spe1.py -v` from `tests/` (green once the
     Part 5 stubs/impl exist).
  2. Interim proof for runner alone: a check that `run_simulation` on SPE1 returns
     `success is True`, `output_dir.exists()`, and that
     `output_dir/SPE1CASE1.SMSPEC` and `.UNSMRY` (or `.ESMRY`) are present.
  3. Negative path: run a deliberately broken deck, assert `success is False`,
     `crash_report is not None`, and that `run_simulation` did not raise.
- Manual cross-check (OPM.md 7.3): `flow --output-dir=OUT SPE1CASE1.DATA` exits 0 and
  writes the eight `CASE.*` files; the wrapper must reproduce the same file set.
- Never-raise proof: unit-level tests for missing binary, missing deck, and timeout
  all return a `SimulationResult`, none raise.

## 9. Future extensions

- Parallel runs: add `mpirun -np N` with the `N <= nproc` / `--oversubscribe` guard
  (OPM.md 7.4, 9); compare against references with `compareECL -i -x` (OPM.md 8.2).
- Binding backend: an alternate `run_simulation` path over
  `opm.simulators.BlackOilSimulator` for in-process stepping, live SummaryState, and
  PYACTION, behind the same `SimulationJob`/`SimulationResult` interface.
- Restart/forecast support (OPM.md 7.12): run a base case, then branch scenario decks
  from a report step via the `RESTART` keyword; `rst_deck` (OPM.md 8.4) can generate
  the restart-deck skeleton. Educationally powerful for "what-if" chats.
- Dry-run pre-check: expose `flow --enable-dry-run=true` as a fast validate mode that
  complements the offline linter (02-linter.md).
- Progress streaming: tail the PRT/terminal output to feed a live progress bar over
  the `/api/run` WebSocket (Stage 5-6).
- Determinism: snapshot the exact argv plus `opmpack`/`opmhash` of the deck alongside
  results for reproducibility (OPM.md 9, 8.5-8.6).
