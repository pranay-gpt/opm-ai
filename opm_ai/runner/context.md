# opm_ai/runner  -  Subprocess wrapper for OPM Flow

**Purpose:** Thin subprocess wrapper around `/usr/bin/flow` (OPM Flow 2026.04). Never raises exceptions; always returns a structured `SimulationResult` with `success: bool`, `output_dir: Path`, `crash_report: CrashReport | None`, and `returncode: int | None`.

## Key invariant
**NEVER raise exceptions.** On any failure (timeout, missing binary, subprocess error, non-zero exit) return `SimulationResult(success=False, crash_report=CrashReport(...), returncode=...)`.

## Thread flag decision
**OMIT `--threads` entirely.** The older `--enable-num-threads` flag is not in the flow 2026.04 catalog (only `--threads-per-process` exists, default 2). Passing an unknown flag makes flow abort (per OPM.md §1). Omit the flag entirely and let flow use its default; revisit `--threads-per-process` only for a deliberate performance mode.

## Exit codes (per OPM.md §9)
| Code | Meaning | Result |
|------|---------|--------|
| 0    | Success | `success=True`, `crash_report=None` |
| 1    | Handled deck error | `success=False`, parse `Error:` from `.PRT`/stderr into `CrashReport` |
| 134  | SIGABRT / core dump (assertion failure) | `success=False`, `CrashReport(message="flow aborted (assertion/core dump)...")` |
| -1   | Timeout / FileNotFoundError / other exception | `success=False`, `CrashReport` with message, `returncode=-1` |

## Command template
```python
argv = [flow_binary, f"--output-dir={output_dir}", str(deck_path)]
proc = subprocess.run(argv, cwd=deck_path.parent, capture_output=True, text=True, timeout=job.timeout, start_new_session=True)
```
- No shell, absolute paths, `output_dir.mkdir(parents=True, exist_ok=True)` before launch
- `cwd=deck_path.parent` so `INCLUDE` paths resolve relative to the deck
- `start_new_session=True` puts flow in its own process group (future-proofs MPI)

## Future work (not implemented)
- Python bindings: `opm.simulators.BlackOilSimulator` at `/usr/lib/python3/dist-packages/opm/simulators` for MPI parallel mode and timestep callbacks
- MPI parallel mode via `mpirun -n N flow ...` (requires the Python binding for proper callback handling)

## Cross-references
- **Full spec:** `docs/conversations/01-runner.md` (sections 4.2-4.5)
- **Contract test:** `tests/integration/test_runner_spe1.py` (asserts `success`, `output_dir`, `WOPT:PROD` KPI)