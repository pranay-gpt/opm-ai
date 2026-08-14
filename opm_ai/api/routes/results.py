"""Results routes: GET /api/results/{job_id} -> KPIs + plots, /snapshots -> ResInsight PNGs,
POST /api/results/{job_id}/resinsight -> launch ResInsight GUI (localhost-gated)."""

import asyncio
import os
import re
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from loguru import logger
from pathlib import Path

from opm_ai.api.job_helpers import job_output_dir
from opm_ai.api.schemas import (
    CategorizedVectorsResponse,
    CsvFrequency,
    KPIsResponse,
    PlotGroupResponse,
    ResinsightLaunchResponse,
    SnapshotsResponse,
)
from opm_ai.api.job_store import get_job
from opm_ai.postprocess.summary import read_summary
from opm_ai.postprocess.kpi import extract_kpis
from opm_ai.postprocess.plots import plot_production, plot_pressure
from opm_ai.postprocess.categorizer import categorize
from opm_ai.postprocess.plot_groups import plot_group as build_plot_group
from opm_ai.postprocess.resample import resample_summary
from opm_ai.postprocess.resinsight_bridge import (
    export_snapshots,
    find_case_file,
    is_resinsight_available,
    launch_resinsight,
)

router = APIRouter()

# PIDs of ResInsight GUI processes launched per job. The dict is process-
# local and dies with the server; for this feature that is acceptable - the
# spawn is detached and survives the server. Tracking is for the
# "one process per job" guard, not for cleanup.
_launched_resinsight_pids: dict[str, int] = {}
_launched_resinsight_lock = threading.Lock()

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_:,.-]+$")

_KNOWN_PLOT_GROUPS = {
    "field_rates", "field_cumulative", "field_derived",
    "well_rates", "well_cumulative", "well_injection",
}


def _split_csv_param(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for p in parts:
        if not _SAFE_ID_RE.match(p):
            raise HTTPException(status_code=400, detail=f"Unsafe identifier in param: {p!r}")
    return parts


def _pid_alive(pid: int) -> bool:
    """True if the process is still running. Returns False for zombies too."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by someone else; that's still alive
        # for our purposes (we own it, this should not happen).
        return True
    return True


def _client_is_loopback(request: Request) -> bool:
    """True when the request originated from loopback.

    ResInsight GUI windows appear on the server's display. A button on a
    remote laptop would open a window on an unattended machine while the UI
    reported success. The gate stops that.

    Tests that drive the route via TestClient (which uses 'testserver' as
    the host) monkeypatch this directly rather than reaching in here.
    """
    if request.client is None:
        return False
    host = request.client.host
    return host in {"127.0.0.1", "::1", "localhost"} or host.startswith("127.")

router = APIRouter()


def _completed_job_output_dir(job_id: str) -> Path:
    """Return the output dir of a completed job or raise 404/400."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed: {job.status}")
    if not job.result:
        raise HTTPException(status_code=400, detail="Job completed but no result data")
    # The Path unwrap itself is the only piece that two routes used to
    # repeat inline (F6.5/F6.6 audit fix). The 404/400 guards stay
    # here because they're results-route-specific policy.
    return job_output_dir(job)


@router.get("/results/{job_id}", response_model=KPIsResponse)
async def get_results(job_id: str) -> KPIsResponse:
    """
    Get KPIs and plots for a completed simulation job.

    Delegates to postprocess.summary.read_summary, postprocess.kpi.extract_kpis,
    postprocess.plots.plot_production, and plot_pressure.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed: {job.status}")

    if not job.result:
        raise HTTPException(status_code=400, detail="Job completed but no result data")

    try:
        output_dir = job_output_dir(job)
        df = read_summary(output_dir)

        if df.empty:
            raise HTTPException(status_code=400, detail="No summary data found in output directory")

        kpis = extract_kpis(df)

        # Generate plots. Plot failures are logged server-side and the
        # entry is set to an empty string rather than stringified JSON
        # (F1.5 audit fix: the old `{"error": ...}` value looked like
        # valid Plotly JSON to the client's JSON.parse but failed later
        # in Plotly.newPlot, leaving a silent empty card).
        plots: dict[str, str] = {}
        try:
            fig_prod = plot_production(df)
            plots["production"] = fig_prod.to_json()
        except Exception:
            logger.exception("Production plot failed for job %s", job_id)
            plots["production"] = ""

        try:
            fig_press = plot_pressure(df)
            plots["pressure"] = fig_press.to_json()
        except Exception:
            logger.exception("Pressure plot failed for job %s", job_id)
            plots["pressure"] = ""

        return KPIsResponse(
            kpis=kpis,
            plots=plots,
            viewer_available=is_resinsight_available() and find_case_file(output_dir) is not None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Results processing failed: {str(e)}")


@router.get("/results/{job_id}/snapshots", response_model=SnapshotsResponse)
async def get_snapshots(job_id: str) -> SnapshotsResponse:
    """
    Export (or reuse cached) ResInsight 3D snapshots for a completed job.

    Runs ResInsight batch mode in a thread executor; the render takes a few
    seconds on first call and is cached in the job's output directory after
    that. Returns filenames servable via GET /results/{job_id}/snapshots/{name}.
    """
    output_dir = _completed_job_output_dir(job_id)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: export_snapshots(output_dir))

    return SnapshotsResponse(
        success=result["success"],
        snapshots=[Path(p).name for p in result["snapshots"]],
        error=result["error"],
        duration_s=result["duration_s"],
    )


@router.get("/results/{job_id}/snapshots/{filename}")
async def get_snapshot_file(job_id: str, filename: str) -> FileResponse:
    """Serve one exported snapshot PNG by filename."""
    output_dir = _completed_job_output_dir(job_id)

    # Filename comes from the URL: forbid separators outright, then confirm
    # the resolved path stays inside the snapshot dir.
    if "/" in filename or "\\" in filename or not filename.endswith(".png"):
        raise HTTPException(status_code=400, detail="Invalid snapshot filename")

    snapshot_dir = (output_dir / "resinsight_snapshots").resolve()
    path = (snapshot_dir / filename).resolve()
    if path.parent != snapshot_dir or not path.is_file():
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {filename}")

    return FileResponse(path, media_type="image/png")


@router.post(
    "/results/{job_id}/resinsight",
    response_model=ResinsightLaunchResponse,
)
async def launch_resinsight_route(job_id: str, request: Request) -> ResinsightLaunchResponse:
    """Launch ResInsight with --case on the server's display.

    Returns immediately; the GUI is detached (start_new_session=True) and
    survives server restarts. Errors before spawn return HTTP error codes:
    - 503 if ResInsight is not available (no binary or no DISPLAY)
    - 404 if the job is unknown
    - 400 if the job is not yet completed
    - 404 if there is no .EGRID/.DATA in the output directory
    - 403 if the request client is not loopback (the GUI would land on
      an unattended machine; this protects against the deployed mode
      the README advertises)

    On success returns {launched: True, pid: N}. If a previous launch for
    this job is still alive, returns {launched: False, pid: N,
    reason: "already running"} instead of spawning a second 91MB GUI.
    """
    if not is_resinsight_available():
        raise HTTPException(
            status_code=503,
            detail="ResInsight not available (no binary or no DISPLAY)",
        )

    if not _client_is_loopback(request):
        raise HTTPException(
            status_code=403,
            detail="ResInsight launch is only available from loopback clients",
        )

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if job.status != "completed" or not job.result:
        raise HTTPException(status_code=400, detail=f"Job not completed: {job.status}")

    output_dir = job_output_dir(job)
    case_file = find_case_file(output_dir)
    if case_file is None:
        raise HTTPException(
            status_code=404,
            detail=f"No .EGRID or .DATA file in {output_dir}",
        )

    # One process per job: check if a previous launch is still alive.
    with _launched_resinsight_lock:
        existing_pid = _launched_resinsight_pids.get(job_id)
        if existing_pid is not None and _pid_alive(existing_pid):
            return ResinsightLaunchResponse(
                launched=False,
                pid=existing_pid,
                reason="already running",
                error=None,
            )

    # Spawn outside the lock - launch_resinsight takes ~50ms (the sleep
    # inside it) and we don't want to block concurrent reads.
    result = await asyncio.get_event_loop().run_in_executor(None, lambda: launch_resinsight(case_file))

    if not result["success"]:
        # Spawn failed - surface as 500 with the bridge's reason. The job
        # and case file checks already passed; the only thing left is a
        # binary/environment problem.
        raise HTTPException(status_code=500, detail=result["error"] or "launch failed")

    pid = result["pid"]
    with _launched_resinsight_lock:
        _launched_resinsight_pids[job_id] = pid

    return ResinsightLaunchResponse(launched=True, pid=pid, reason=None, error=None)


@router.get("/results/{job_id}/categories", response_model=CategorizedVectorsResponse)
async def get_categories(job_id: str) -> CategorizedVectorsResponse:
    """Categorise summary columns into priority vector families."""
    output_dir = _completed_job_output_dir(job_id)
    df = read_summary(output_dir)
    cats = categorize(df)
    return CategorizedVectorsResponse(**cats)


@router.get("/results/{job_id}/plot_group/{group}", response_model=PlotGroupResponse)
async def get_plot_group(
    job_id: str,
    group: str,
    wells: str | None = None,
    vectors: str | None = None,
    log: bool = False,
) -> PlotGroupResponse:
    """Build a Plotly figure for one priority vector group."""
    if group not in _KNOWN_PLOT_GROUPS:
        # Unknown group is a 200 with empty json so the client shows the
        # standard empty-state rather than a hard error. The route logs
        # the actual trace when plot generation fails (below).
        return PlotGroupResponse(group=group, figure_json="", error=f"Unknown group: {group}")

    output_dir = _completed_job_output_dir(job_id)
    df = read_summary(output_dir)
    if df.empty:
        return PlotGroupResponse(group=group, figure_json="", error="Empty summary")

    well_list = _split_csv_param(wells)
    vector_list = _split_csv_param(vectors) or None

    try:
        fig = build_plot_group(group, df, well_list, vector_list, log_scale=log)
        return PlotGroupResponse(group=group, figure_json=fig.to_json(), error=None)
    except Exception:
        logger.exception("Plot group %s failed for job %s", group, job_id)
        return PlotGroupResponse(group=group, figure_json="", error="plot generation failed")


@router.get("/results/{job_id}/csv")
async def get_csv(
    job_id: str,
    group: str,
    vectors: str,
    freq: CsvFrequency = CsvFrequency.NATIVE,
) -> Response:
    """Return a CSV slice of the summary DataFrame at the requested frequency."""
    _split_csv_param(vectors)  # validates; raises 400 on bad chars

    output_dir = _completed_job_output_dir(job_id)
    df = read_summary(output_dir)
    if df.empty:
        return Response(content="TIME\n", media_type="text/csv")

    requested = [v.strip() for v in vectors.split(",") if v.strip()]
    present = [v for v in requested if v in df.columns]
    if not present:
        return Response(content="TIME\n", media_type="text/csv")

    slice_df = df[["TIME", *present]].copy()
    if freq != CsvFrequency.NATIVE:
        slice_df = resample_summary(slice_df, freq.value)

    csv_body = slice_df.to_csv(index=False)
    return Response(content=csv_body, media_type="text/csv")