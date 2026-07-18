"""Simulation runner for OPM Flow."""

import re
import subprocess
from pathlib import Path

from opm_ai.runner.models import CrashReport, SimulationJob, SimulationResult
from opm_ai.settings import settings


def _parse_crash_report(stderr: str, returncode: int) -> CrashReport:
    """Parse stderr for crash information and extract keyword/line if possible."""
    message = stderr.strip() if stderr else f"Process exited with code {returncode}"
    keyword: str | None = None
    line: int | None = None

    # Look for "Error:" pattern and try to extract keyword/line
    error_lines = [line for line in stderr.splitlines() if "Error:" in line]
    if error_lines:
        last_error = error_lines[-1]
        # Try to extract keyword: "Problem with keyword DATES" -> "DATES"
        keyword_match = re.search(r"keyword\s+([A-Z0-9_]+)", last_error, re.IGNORECASE)
        if keyword_match:
            keyword = keyword_match.group(1)
        # Try to extract line number: "line 123" or "at line 123"
        line_match = re.search(r"line\s+(\d+)", last_error, re.IGNORECASE)
        if line_match:
            line = int(line_match.group(1))
        message = last_error.strip()

    # Special handling for SIGABRT (exit code 134)
    if returncode == 134:
        message = f"flow aborted (assertion/core dump): {message}"
    elif returncode == 1:
        message = f"flow error: {message}"

    return CrashReport(keyword=keyword, line=line, message=message)


def _parse_timeout_crash(timeout: int) -> CrashReport:
    """Create a crash report for timeout."""
    return CrashReport(
        keyword=None,
        line=None,
        message=f"Simulation timed out after {timeout} seconds",
    )


def _parse_file_not_found_crash(binary_path: str) -> CrashReport:
    """Create a crash report for missing binary."""
    return CrashReport(
        keyword=None,
        line=None,
        message=f"Flow binary not found at {binary_path}",
    )


def _parse_exception_crash(exc: Exception) -> CrashReport:
    """Create a crash report for unexpected exceptions."""
    return CrashReport(
        keyword=None,
        line=None,
        message=f"Unexpected error: {exc!r}",
    )


def run_simulation(job: SimulationJob) -> SimulationResult:
    """
    Run OPM Flow simulation.

    Args:
        job: SimulationJob configuration.

    Returns:
        SimulationResult with success status and output paths or crash report.
        NEVER raises; always returns a result.
    """
    flow_binary = str(settings.flow_path)
    output_dir = job.output_dir
    deck_path = job.deck_path

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command - OMIT --threads per spec (flow 2026.04 compatibility)
    argv = [
        flow_binary,
        f"--output-dir={output_dir}",
        str(deck_path),
    ]

    try:
        proc = subprocess.run(
            argv,
            cwd=deck_path.parent,
            capture_output=True,
            text=True,
            timeout=job.timeout,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired:
        return SimulationResult(
            success=False,
            output_dir=output_dir,
            crash_report=_parse_timeout_crash(job.timeout),
            returncode=-1,
        )
    except FileNotFoundError:
        return SimulationResult(
            success=False,
            output_dir=output_dir,
            crash_report=_parse_file_not_found_crash(flow_binary),
            returncode=-1,
        )
    except Exception as exc:
        return SimulationResult(
            success=False,
            output_dir=output_dir,
            crash_report=_parse_exception_crash(exc),
            returncode=-1,
        )

    # Handle exit codes per spec (section 4.3)
    returncode = proc.returncode

    if returncode == 0:
        # Success - discover output files
        smspec_files = list(output_dir.glob("*.SMSPEC"))
        unrst_files = list(output_dir.glob("*.UNRST"))

        return SimulationResult(
            success=True,
            output_dir=output_dir,
            crash_report=None,
            returncode=returncode,
        )

    # Failure - parse crash report from stderr
    crash_report = _parse_crash_report(proc.stderr, returncode)
    return SimulationResult(
        success=False,
        output_dir=output_dir,
        crash_report=crash_report,
        returncode=returncode,
    )