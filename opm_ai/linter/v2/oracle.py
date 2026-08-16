"""Flow-as-oracle validator for the v2 linter.

Runs `flow --enable-dry-run=true` on a deck and classifies the verdict.
This is the ground truth that every v2 linter change must respect.

The oracle distinguishes:
  - known-good: Flow exits 0 with no ERROR/FATAL lines in stderr
  - known-bad:  Flow exits non-zero, OR exits 0 with ERROR/FATAL in stderr

A known-bad verdict is *informative*, not authoritative — it tells us Flow
rejected the deck, but the reason may be a Flow bug, an OPM-Flow-unsupported
keyword, or a real deck error. The v2 linter should reproduce the Flow
verdict on every known-good deck, and should at minimum produce a more
informative diagnostic on every known-bad deck (line numbers, symbol-table
context) than Flow does.

Validation command is `flow --enable-dry-run=true --output-dir=DIR DECK`
(bare `flow --check` is rejected by flow 2026.04).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_S = 30

# Match ERROR and FATAL tokens in Flow stderr. WARN is excluded — many
# legitimate decks produce warnings.
_ERROR_RE = re.compile(r"\b(ERROR|FATAL|EXCEPTION)\b", re.IGNORECASE)

# Match Flow's fatal markers in stdout. Flow distinguishes:
#   - "Warning: ..." → deck is still accepted
#   - "Error: ..."   → deck is rejected
#   - "Fatal error" or "Failed to create" → deck is rejected
# We match the error/fatal cases only.
_FATAL_STDOUT_RE = re.compile(
    r"(^Error: |"
    r"failed to create valid eclipselease|"
    r"problem with keyword|"
    r"a fatal error has occurred|"
    r"^\s*Fatal error)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class FlowVerdict:
    """Verdict from `flow --enable-dry-run=true` on a deck."""

    deck_path: Path
    exit_code: int
    stderr: str
    stdout_tail: str  # last 2KB only — full output can be MB-scale
    error_lines: list[str]  # lines containing ERROR/FATAL/EXCEPTION
    fatal_in_stdout: bool
    wallclock_ms: int
    timeout: bool = False

    @property
    def passed(self) -> bool:
        """True iff Flow accepts the deck without errors.

        Two conditions for acceptance:
        1. exit code 0
        2. no ERROR/FATAL/EXCEPTION lines in stderr
        3. no fatal markers in stdout (Flow can log a fatal error and
           still exit 0 in some edge cases)
        """
        return (
            self.exit_code == 0
            and len(self.error_lines) == 0
            and not self.fatal_in_stdout
            and not self.timeout
        )

    @property
    def failure_reason(self) -> str:
        """Human-readable reason for failure (empty if passed)."""
        if self.timeout:
            return f"timeout after {self.wallclock_ms}ms"
        if self.exit_code == -2:
            return f"oracle error: {self.error_lines[0] if self.error_lines else 'unknown'}"
        if self.exit_code != 0:
            return f"flow exit {self.exit_code}"
        if self.fatal_in_stdout:
            return "fatal error in stdout"
        if self.error_lines:
            return f"{len(self.error_lines)} error line(s); first: {self.error_lines[0][:120]}"
        return ""


@dataclass
class OracleConfig:
    """Configuration for the Flow oracle."""

    flow_binary: str = "flow"
    timeout_s: int = DEFAULT_TIMEOUT_S
    output_dir: Path | None = None  # None = use a temp dir
    cwd: Path | None = None  # None = use the deck's parent directory
    dry_run_flag: str = "--enable-dry-run=true"


def find_flow() -> str | None:
    """Locate the `flow` binary. Returns None if not installed."""
    return shutil.which("flow")


def run_flow(
    deck_path: Path,
    config: OracleConfig | None = None,
) -> FlowVerdict:
    """Run `flow --enable-dry-run=true` on a deck and return the verdict.

    Args:
        deck_path: Absolute path to the .DATA file.
        config: OracleConfig; uses defaults if None.

    Returns:
        FlowVerdict with exit code, stderr, and error classification.

    Raises:
        FileNotFoundError: if the deck doesn't exist.
        RuntimeError: if `flow` is not on PATH.
    """
    if config is None:
        config = OracleConfig()
    deck_path = Path(deck_path).resolve()
    if not deck_path.exists():
        raise FileNotFoundError(f"deck not found: {deck_path}")

    flow_bin = find_flow()
    if flow_bin is None:
        raise RuntimeError(
            "flow binary not found on PATH; install OPM Flow 2026.04+"
        )

    # Output dir: temp if not specified
    if config.output_dir is not None:
        out_dir = Path(config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        cleanup_out = False
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="flow_oracle_"))
        cleanup_out = True

    cwd = Path(config.cwd).resolve() if config.cwd else deck_path.parent
    # Compute the deck path relative to cwd, so Flow can find it. If the
    # deck is not under cwd (e.g. user passes a deck outside the cwd tree),
    # fall back to the absolute path.
    try:
        deck_rel = deck_path.relative_to(cwd)
    except ValueError:
        deck_rel = deck_path

    cmd = [
        flow_bin,
        config.dry_run_flag,
        f"--output-dir={out_dir}",
        str(deck_rel),
    ]

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=config.timeout_s,
        )
        stderr = result.stderr or ""
        stdout = result.stdout or ""
        exit_code = result.returncode
        timed_out = False
    except subprocess.TimeoutExpired as e:
        stderr = (e.stderr.decode() if e.stderr else "") or ""
        stdout = (e.stdout.decode() if e.stdout else "") or ""
        exit_code = -1
        timed_out = True
    t1 = time.monotonic()
    wallclock_ms = int((t1 - t0) * 1000)

    error_lines = [
        line.strip()
        for line in stderr.splitlines()
        if _ERROR_RE.search(line)
    ]
    fatal_in_stdout = bool(_FATAL_STDOUT_RE.search(stdout))

    if cleanup_out:
        shutil.rmtree(out_dir, ignore_errors=True)

    return FlowVerdict(
        deck_path=deck_path,
        exit_code=exit_code,
        stderr=stderr,
        stdout_tail=stdout[-2048:] if stdout else "",
        error_lines=error_lines,
        fatal_in_stdout=fatal_in_stdout,
        wallclock_ms=wallclock_ms,
        timeout=timed_out,
    )


def classify_fixtures(
    deck_paths: list[Path],
    config: OracleConfig | None = None,
) -> dict[Path, FlowVerdict]:
    """Run Flow on a list of decks and return a dict of verdicts.

    Args:
        deck_paths: List of deck paths (each must exist).
        config: OracleConfig; uses defaults if None.

    Returns:
        Dict mapping deck_path -> FlowVerdict.
    """
    if config is None:
        config = OracleConfig()
    verdicts: dict[Path, FlowVerdict] = {}
    for deck in deck_paths:
        try:
            verdicts[Path(deck).resolve()] = run_flow(Path(deck), config)
        except (FileNotFoundError, RuntimeError) as e:
            verdicts[Path(deck).resolve()] = FlowVerdict(
                deck_path=Path(deck).resolve(),
                exit_code=-2,
                stderr=str(e),
                stdout_tail="",
                error_lines=[str(e)],
                fatal_in_stdout=False,
                wallclock_ms=0,
                timeout=False,
            )
    return verdicts


def categorize_failure(verdict: FlowVerdict) -> str:
    """Categorize a known-bad verdict for diagnostic purposes.

    Returns one of: 'flow-exit', 'flow-stderr-error',
    'flow-stdout-fatal', 'flow-timeout', 'oracle-error'.
    """
    if verdict.timeout:
        return "flow-timeout"
    if verdict.exit_code == -2:
        return "oracle-error"
    if verdict.exit_code != 0:
        return "flow-exit"
    if verdict.fatal_in_stdout:
        return "flow-stdout-fatal"
    if verdict.error_lines:
        return "flow-stderr-error"
    return "unknown"
