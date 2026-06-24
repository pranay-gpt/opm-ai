# opm_ai/runner/runner.py
import subprocess
import time
import re
import os
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

from .models import (
    SimulationJob, SimulationResult,
    SimulationStatus, CrashReport
)

load_dotenv()

# OPM Flow binary path — from .env or Ubuntu PPA default
FLOW_BINARY = Path(os.getenv("OPM_FLOW_BINARY", "/usr/bin/flow"))


def run_simulation(job: SimulationJob) -> SimulationResult:
    """
    Execute OPM Flow for the given SimulationJob.
    Returns a SimulationResult regardless of success or failure.
    Never raises — all errors are captured in CrashReport objects.

    Note: --threads flag is intentionally omitted.
    OPM Flow on Ubuntu 24.04 (ARM64) does not accept --threads as a
    runtime argument. Parallelism is controlled via MPI (mpirun) which
    is a separate concern handled outside this function.
    """
    deck = Path(job.deck_path).resolve()
    output_dir = Path(job.output_dir).resolve() if job.output_dir else deck.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    if not deck.exists():
        return SimulationResult(
            job=job,
            status=SimulationStatus.FAILED,
            elapsed_seconds=0.0,
            crash_reports=[CrashReport(
                severity="ERROR",
                message=f"Deck file not found: {deck}"
            )]
        )

    if not FLOW_BINARY.exists():
        return SimulationResult(
            job=job,
            status=SimulationStatus.FAILED,
            elapsed_seconds=0.0,
            crash_reports=[CrashReport(
                severity="ERROR",
                message=(
                    f"OPM Flow binary not found at {FLOW_BINARY}. "
                    "Install with: sudo apt-get install libopm-simulators-bin"
                )
            )]
        )

    # Build command — no --threads flag (not supported on all OPM builds)
    cmd = [
        str(FLOW_BINARY),
        str(deck),
        f"--output-dir={output_dir}",
    ]

    logger.info(f"Running OPM Flow: {' '.join(cmd)}")
    start = time.time()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=job.timeout_seconds,
            cwd=str(deck.parent),
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return SimulationResult(
            job=job,
            status=SimulationStatus.FAILED,
            elapsed_seconds=elapsed,
            crash_reports=[CrashReport(
                severity="ERROR",
                message=f"Simulation timed out after {job.timeout_seconds}s"
            )]
        )

    elapsed = time.time() - start
    crash_reports = _parse_opm_output(proc.stdout + proc.stderr)

    # Locate output files
    stem = deck.stem
    summary_file = output_dir / f"{stem}.SMSPEC"
    restart_file = output_dir / f"{stem}.UNRST"

    status = (
        SimulationStatus.SUCCESS
        if proc.returncode == 0 and summary_file.exists()
        else SimulationStatus.FAILED
    )

    logger.info(
        f"Simulation {status.value} in {elapsed:.1f}s — "
        f"{len([r for r in crash_reports if r.severity == 'ERROR'])} errors, "
        f"{len([r for r in crash_reports if r.severity == 'WARNING'])} warnings"
    )

    return SimulationResult(
        job=job,
        status=status,
        elapsed_seconds=elapsed,
        summary_file=summary_file if summary_file.exists() else None,
        restart_file=restart_file if restart_file.exists() else None,
        crash_reports=crash_reports,
        raw_stdout=proc.stdout,
        raw_stderr=proc.stderr,
    )


# ── OPM output parser ─────────────────────────────────────────────────────────

_ERROR_RE   = re.compile(r"(?i)\bError\b[:\s]+(.+)")
_WARNING_RE = re.compile(r"(?i)\bWarning\b[:\s]+(.+)")
_KEYWORD_RE = re.compile(r"\b([A-Z]{4,12})\b")


def _parse_opm_output(text: str) -> list[CrashReport]:
    """Parse OPM stdout/stderr into structured CrashReport objects."""
    reports: list[CrashReport] = []
    seen: set[str] = set()

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for pattern, severity in [(_ERROR_RE, "ERROR"), (_WARNING_RE, "WARNING")]:
            m = pattern.search(line)
            if m:
                msg = m.group(1).strip()
                if msg not in seen:
                    seen.add(msg)
                    keyword_match = _KEYWORD_RE.search(msg)
                    reports.append(CrashReport(
                        severity=severity,
                        message=msg,
                        keyword=keyword_match.group(1) if keyword_match else None,
                    ))
                break

    return reports
