"""Simulation runner for OPM Flow."""

import subprocess
import time
from pathlib import Path
from typing import Optional

from opm_ai.runner.models import CrashReport, SimulationJob, SimulationResult


def run_simulation(job: SimulationJob) -> SimulationResult:
    """
    Run OPM Flow simulation.

    Args:
        job: SimulationJob configuration.

    Returns:
        SimulationResult with success status and output paths.
    """
    # Ensure output directory exists
    job.output_dir.mkdir(parents=True, exist_ok=True)

    deck_name = job.deck_path.stem
    stdout_log = job.output_dir / f"{deck_name}.out"
    stderr_log = job.output_dir / f"{deck_name}.err"

    # Build command - OMIT --threads per BUILD_GUIDE
    # Use = syntax for output-dir per flow CLI
    cmd = [
        job.flow_binary,
        str(job.deck_path),
        f"--output-dir={job.output_dir}",
    ]

    try:
        with open(stdout_log, "w") as sout, open(stderr_log, "w") as serr:
            start_time = time.time()
            proc = subprocess.run(
                cmd,
                stdout=sout,
                stderr=serr,
                timeout=job.timeout,
                cwd=job.output_dir,
            )
            elapsed = time.time() - start_time

        # Check for output files
        smspec_files = list(job.output_dir.glob("*.SMSPEC"))
        unrst_files = list(job.output_dir.glob("*.UNRST"))

        if proc.returncode == 0 and smspec_files:
            return SimulationResult(
                success=True,
                job=job,
                output_dir=job.output_dir,
                smspec_path=smspec_files[0],
                unrst_path=unrst_files[0] if unrst_files else None,
            )
        else:
            # Read stderr for crash report
            stderr_content = stderr_log.read_text() if stderr_log.exists() else ""
            stdout_content = stdout_log.read_text() if stdout_log.exists() else ""
            error_type = _classify_error(proc.returncode, stderr_content)
            return SimulationResult(
                success=False,
                job=job,
                output_dir=job.output_dir,
                crash_report=CrashReport(
                    exit_code=proc.returncode,
                    stderr=stderr_content,
                    stdout=stdout_content,
                    error_type=error_type,
                ),
            )

    except subprocess.TimeoutExpired:
        return SimulationResult(
            success=False,
            job=job,
            output_dir=job.output_dir,
            crash_report=CrashReport(
                exit_code=-1,
                stderr=f"Simulation timed out after {job.timeout} seconds",
                stdout="",
                error_type="TIMEOUT",
            ),
        )
    except FileNotFoundError:
        return SimulationResult(
            success=False,
            job=job,
            output_dir=job.output_dir,
            crash_report=CrashReport(
                exit_code=-1,
                stderr=f"Flow binary not found at {job.flow_binary}",
                stdout="",
                error_type="INPUT_ERROR",
            ),
        )
    except Exception as e:
        return SimulationResult(
            success=False,
            job=job,
            output_dir=job.output_dir,
            crash_report=CrashReport(
                exit_code=-1,
                stderr=str(e),
                stdout="",
                error_type="CRASH",
            ),
        )


def _classify_error(exit_code: int, stderr: str) -> str:
    """Classify error type from exit code and stderr."""
    stderr_lower = stderr.lower()
    if "error" in stderr_lower and ("keyword" in stderr_lower or "syntax" in stderr_lower or "parse" in stderr_lower):
        return "INPUT_ERROR"
    if "numerical" in stderr_lower or "convergence" in stderr_lower or "linear solver" in stderr_lower:
        return "NUMERICAL"
    if exit_code == -1 or "timeout" in stderr_lower:
        return "TIMEOUT"
    return "CRASH"