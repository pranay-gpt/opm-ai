"""ResInsight bridge: 3D snapshot export via the batch CLI.

The packaged ResInsight 2026.06.0 binary on this host is compiled without
gRPC support (`--server` never binds a port, no grpc libs linked), so the
`rips` Python API cannot connect. Snapshots also require a real GL context:
QT_QPA_PLATFORM=offscreen segfaults with "QOpenGLWidget is not supported".

The one working headless path (verified 2026-07-20) is the batch CLI against
a live X display:

    DISPLAY=:0 QT_QPA_PLATFORM=xcb ResInsight --case CASE.EGRID \
        --savesnapshots views --snapshotfolder DIR --size W H

ResInsight renders the default 3D view (SOIL at the first time step per user
preferences) and exits on its own. This module wraps that invocation with the
runner's never-raise contract: every function returns a result dict, never
throws.
"""

import os
import subprocess
import time
from pathlib import Path

from opm_ai.settings import settings

SNAPSHOT_SUBDIR = "resinsight_snapshots"
DEFAULT_TIMEOUT_S = 180
DEFAULT_SIZE = (1200, 900)


def _display() -> str | None:
    """Return the X display to render on, or None if there is none."""
    return os.environ.get("DISPLAY") or None


def is_resinsight_available() -> bool:
    """True when the ResInsight executable exists and an X display is set.

    Cheap checks only: no process is launched. A present display can still
    be unreachable (e.g. stale DISPLAY in a container); export_snapshots()
    reports that as a failed result rather than raising.
    """
    return Path(settings.resinsight_executable).is_file() and _display() is not None


def find_case_file(output_dir: Path) -> Path | None:
    """Return the .EGRID (preferred) or .DATA file in a simulation output dir."""
    output_dir = Path(output_dir)
    for pattern in ("*.EGRID", "*.DATA"):
        matches = sorted(output_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def export_snapshots(
    output_dir: Path,
    snapshot_dir: Path | None = None,
    size: tuple[int, int] = DEFAULT_SIZE,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Export 3D view snapshots for a completed simulation via ResInsight batch mode.

    Args:
        output_dir: Simulation output directory containing .EGRID/.DATA.
        snapshot_dir: Destination for PNGs. Defaults to
            output_dir/resinsight_snapshots. Existing PNGs there are reused
            (acts as a cache); pass a clean directory to force re-render.
        size: Snapshot width and height in pixels.
        timeout_s: Kill ResInsight after this many seconds.

    Returns:
        Dict with keys: success (bool), snapshots (list of str paths),
        error (str or None), duration_s (float).
    """
    started = time.monotonic()

    def result(success: bool, snapshots: list[str], error: str | None) -> dict:
        return {
            "success": success,
            "snapshots": snapshots,
            "error": error,
            "duration_s": round(time.monotonic() - started, 2),
        }

    if not Path(settings.resinsight_executable).is_file():
        return result(False, [], f"ResInsight executable not found: {settings.resinsight_executable}")
    if _display() is None:
        return result(False, [], "No X display available (DISPLAY unset); ResInsight snapshots need a live display")

    output_dir = Path(output_dir)
    case_file = find_case_file(output_dir)
    if case_file is None:
        return result(False, [], f"No .EGRID or .DATA file found in {output_dir}")

    snapshot_dir = Path(snapshot_dir) if snapshot_dir else output_dir / SNAPSHOT_SUBDIR
    try:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return result(False, [], f"Cannot create snapshot dir {snapshot_dir}: {e}")

    cached = sorted(snapshot_dir.glob("*.png"))
    if cached:
        return result(True, [str(p) for p in cached], None)

    cmd = [
        str(settings.resinsight_executable),
        "--case", str(case_file),
        "--savesnapshots", "views",
        "--snapshotfolder", str(snapshot_dir),
        "--size", str(size[0]), str(size[1]),
    ]
    env = {**os.environ, "QT_QPA_PLATFORM": "xcb"}

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return result(False, [], f"ResInsight timed out after {timeout_s}s")
    except OSError as e:
        return result(False, [], f"Failed to launch ResInsight: {e}")

    pngs = sorted(snapshot_dir.glob("*.png"))
    if not pngs:
        stderr_tail = (proc.stderr or "").strip().splitlines()[-3:]
        detail = "; ".join(stderr_tail) if stderr_tail else f"exit code {proc.returncode}"
        return result(False, [], f"ResInsight produced no snapshots ({detail})")

    return result(True, [str(p) for p in pngs], None)
