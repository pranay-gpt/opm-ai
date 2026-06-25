"""ResInsight gRPC bridge — Part 5.

Strategy (dual-mode, graceful degradation)
------------------------------------------
Mode A — Sidecar (preferred in Docker compose):
  ResInsight is already running as a separate service on RESINSIGHT_HOST:RESINSIGHT_PORT.
  We connect immediately via rips without launching a process.

Mode B — Local launch (fallback for bare-metal users):
  We subprocess.Popen() resinsight --server PORT and wait for it to be ready.
  RESINSIGHT_BIN env var or 'resinsight' on PATH.

If rips is not installed, we log a warning and return False — never crash the pipeline.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import os
import logging
import time

log = logging.getLogger(__name__)

RESINSIGHT_HOST = os.getenv("RESINSIGHT_HOST", "localhost")
RESINSIGHT_PORT = int(os.getenv("RESINSIGHT_PORT", "50051"))
RESINSIGHT_BIN = os.getenv("RESINSIGHT_BIN", "resinsight")


def open_in_resinsight(
    result,                         # SimulationResult
    export_snapshots: bool = True,  # export PNG 3-D snapshots
    snapshot_dir: Optional[Path] = None,
    timesteps: Optional[list[int]] = None,  # None = first + middle + last
) -> bool:
    """Open a completed simulation in ResInsight and optionally export snapshots.

    Returns True if ResInsight was reached and the case was loaded successfully.
    """
    try:
        import rips  # type: ignore
    except ImportError:
        log.warning("rips not installed — ResInsight bridge disabled. "
                    "pip install rips to enable 3-D visualisation.")
        return False

    if not result.succeeded:
        log.warning("ResInsight bridge: simulation did not succeed, skipping.")
        return False

    instance = _get_or_launch_resinsight(rips)
    if instance is None:
        return False

    try:
        case = _load_case(instance, result)
        if case is None:
            return False

        if export_snapshots:
            snap_dir = snapshot_dir or result.job.output_dir or result.job.deck_path.parent
            Path(snap_dir).mkdir(parents=True, exist_ok=True)
            _export_snapshots(instance, case, snap_dir, timesteps)

        log.info("ResInsight: case loaded successfully — %s", result.job.deck_path.stem)
        return True

    except Exception as exc:
        log.error("ResInsight bridge error: %s", exc)
        return False


def _get_or_launch_resinsight(rips):
    """Try sidecar connection first; fall back to local launch."""
    # Mode A: sidecar already running
    try:
        instance = rips.Instance.find(port=RESINSIGHT_PORT, host=RESINSIGHT_HOST)
        if instance:
            log.info("ResInsight: connected to sidecar at %s:%d",
                     RESINSIGHT_HOST, RESINSIGHT_PORT)
            return instance
    except Exception:
        pass

    # Mode B: launch locally
    return _launch_local(rips)


def _launch_local(rips):
    """Launch resinsight --server PORT as a subprocess, wait up to 15s."""
    import subprocess
    port = RESINSIGHT_PORT
    try:
        proc = subprocess.Popen(
            [RESINSIGHT_BIN, "--server", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        log.warning("ResInsight binary not found at '%s'. "
                    "Set RESINSIGHT_BIN env var or install ResInsight.", RESINSIGHT_BIN)
        return None

    log.info("ResInsight: launched locally on port %d, waiting for gRPC…", port)
    for _ in range(30):  # 15 seconds
        time.sleep(0.5)
        try:
            instance = rips.Instance.find(port=port)
            if instance:
                log.info("ResInsight: local instance ready.")
                return instance
        except Exception:
            pass

    log.error("ResInsight: timed out waiting for local instance.")
    proc.terminate()
    return None


def _load_case(instance, result):
    """Load the OPM case into ResInsight."""
    # ResInsight loads from the .SMSPEC path or the base deck path
    case_path = str(result.summary_file or result.job.deck_path)
    try:
        cases = instance.project.loadCaseFromFile(case_path)
        # loadCaseFromFile returns a list or a single case depending on rips version
        case = cases[0] if isinstance(cases, list) else cases
        return case
    except Exception as exc:
        log.error("ResInsight: failed to load case '%s': %s", case_path, exc)
        return None


def _export_snapshots(instance, case, snap_dir: Path, timesteps: Optional[list[int]]):
    """Export 3-D saturation and pressure PNGs at selected timesteps."""
    try:
        ts_count = case.timeStepCount() if hasattr(case, "timeStepCount") else 1
    except Exception:
        ts_count = 1

    if timesteps is None:
        mid = ts_count // 2
        timesteps = list({0, mid, ts_count - 1})

    views = instance.project.views(case)
    view = views[0] if views else None
    if view is None:
        return

    for ts in timesteps:
        try:
            view.setCurrentTimeStep(ts)
            # Export SOIL (oil saturation) snapshot
            png_soil = str(snap_dir / f"resinsight_SOIL_ts{ts:04d}.png")
            instance.project.exportVisibleCells(
                export_folder=str(snap_dir),
                export_format="PNG",
                image_width=1200,
                image_height=800,
            )
            log.info("ResInsight: exported snapshot timestep %d", ts)
        except Exception as exc:
            log.warning("ResInsight: snapshot export failed at ts %d: %s", ts, exc)
