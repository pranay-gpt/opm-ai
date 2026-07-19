"""Simulation runner for OPM Flow."""

import re
import time
import subprocess
from pathlib import Path

from opm_ai.runner.models import CrashReport, SimulationJob, SimulationResult
from opm_ai.settings import settings

# Output extensions flow writes for CASE.DATA (01-runner.md section 4.5)
_OUTPUT_EXTENSIONS = ("SMSPEC", "UNSMRY", "ESMRY", "UNRST", "EGRID", "INIT", "PRT", "DBG")


def _parse_crash_report(stderr: str, prt_text: str, returncode: int) -> CrashReport:
    """Parse PRT (primary) and stderr for crash information.

    Flow's parse errors do NOT always carry an 'Error:' prefix - e.g.
    'Problem with keyword INVALID_KEYWORD' / 'In /path/deck.DATA line 30'
    arrive as bare stderr lines - so keyword/line extraction scans ALL lines.
    """
    keyword: str | None = None
    line: int | None = None
    message = ""

    combined = (prt_text or "") + "\n" + (stderr or "")

    # message: last line containing Error:/Simulation aborted, else last
    # non-empty stderr line (01-runner.md section 4.4)
    candidates = [
        ln for ln in combined.splitlines()
        if "Error:" in ln or "Simulation aborted" in ln
    ]
    if candidates:
        message = candidates[-1].strip()
    else:
        stderr_lines = [ln.strip() for ln in (stderr or "").splitlines() if ln.strip()]
        if stderr_lines:
            message = stderr_lines[-1]

    for ln in combined.splitlines():
        if keyword is None:
            keyword_match = re.search(r"keyword\s+([A-Z0-9_]+)", ln)
            if keyword_match:
                keyword = keyword_match.group(1)
                if not message:
                    message = ln.strip()
        if line is None:
            line_match = re.search(r"\bline\s+(\d+)", ln, re.IGNORECASE)
            if line_match:
                line = int(line_match.group(1))

    if not message:
        message = f"Process exited with code {returncode}"

    if returncode == 134:
        message = f"flow aborted (assertion/core dump): {message}"
    elif returncode == 1:
        message = f"flow error: {message}"

    return CrashReport(keyword=keyword, line=line, message=message)


def _collect_warnings(prt_text: str) -> list[str]:
    """Collect Warning: lines from the PRT (deduplicated, order-preserving)."""
    seen: set[str] = set()
    warnings: list[str] = []
    for ln in (prt_text or "").splitlines():
        stripped = ln.strip()
        if "Warning:" in stripped and stripped not in seen:
            seen.add(stripped)
            warnings.append(stripped)
    return warnings


def _discover_outputs(output_dir: Path, stem: str) -> dict[str, Path]:
    """Map extension -> path for the case outputs that exist."""
    found: dict[str, Path] = {}
    for ext in _OUTPUT_EXTENSIONS:
        p = output_dir / f"{stem.upper()}.{ext}"
        if not p.exists():
            p = output_dir / f"{stem}.{ext}"
        if p.exists():
            found[ext] = p
    return found


def _read_prt(output_dir: Path, stem: str) -> str:
    """Read the PRT file if present; empty string otherwise. Never raises."""
    for name in (f"{stem.upper()}.PRT", f"{stem}.PRT"):
        p = output_dir / name
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return ""
    return ""


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
    started = time.monotonic()

    try:
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build command - OMIT --threads per spec (flow 2026.04 compatibility)
        argv = [
            flow_binary,
            f"--output-dir={output_dir}",
            str(deck_path),
        ]

        proc = subprocess.run(
            argv,
            cwd=deck_path.parent if deck_path.parent.is_dir() else None,
            capture_output=True,
            text=True,
            timeout=job.timeout,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired as exc:
        return SimulationResult(
            success=False,
            output_dir=output_dir,
            crash_report=CrashReport(
                message=f"Simulation timed out after {job.timeout} seconds"),
            returncode=-1,
            timed_out=True,
            duration_s=time.monotonic() - started,
            stdout=(exc.stdout or b"").decode("utf-8", "replace")
                   if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=(exc.stderr or b"").decode("utf-8", "replace")
                   if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
        )
    except FileNotFoundError:
        return SimulationResult(
            success=False,
            output_dir=output_dir,
            crash_report=CrashReport(
                message=f"Flow binary not found at {flow_binary}"),
            returncode=-1,
            duration_s=time.monotonic() - started,
        )
    except Exception as exc:
        return SimulationResult(
            success=False,
            output_dir=output_dir,
            crash_report=CrashReport(message=f"Unexpected error: {exc!r}"),
            returncode=-1,
            duration_s=time.monotonic() - started,
        )

    duration = time.monotonic() - started
    returncode = proc.returncode
    stem = deck_path.stem
    prt_text = _read_prt(output_dir, stem)
    outputs = _discover_outputs(output_dir, stem)

    if returncode == 0:
        return SimulationResult(
            success=True,
            output_dir=output_dir,
            crash_report=None,
            returncode=returncode,
            duration_s=duration,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            warnings=_collect_warnings(prt_text),
            summary_files=outputs,
            prt_path=outputs.get("PRT"),
        )

    return SimulationResult(
        success=False,
        output_dir=output_dir,
        crash_report=_parse_crash_report(proc.stderr, prt_text, returncode),
        returncode=returncode,
        duration_s=duration,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        warnings=_collect_warnings(prt_text),
        summary_files=outputs,
        prt_path=outputs.get("PRT"),
    )
