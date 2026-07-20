"""Results routes: GET /api/results/{job_id} -> KPIs + plots, /snapshots -> ResInsight PNGs"""

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from opm_ai.api.schemas import KPIsResponse, SnapshotsResponse
from opm_ai.api.job_store import get_job
from opm_ai.postprocess.summary import read_summary
from opm_ai.postprocess.kpi import extract_kpis
from opm_ai.postprocess.plots import plot_production, plot_pressure
from opm_ai.postprocess.resinsight_bridge import export_snapshots

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
    return Path(job.result.output_dir)


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
        output_dir = Path(job.result.output_dir)
        df = read_summary(output_dir)

        if df.empty:
            raise HTTPException(status_code=400, detail="No summary data found in output directory")

        kpis = extract_kpis(df)

        # Generate plots
        plots = {}
        try:
            fig_prod = plot_production(df)
            plots["production"] = fig_prod.to_json()
        except Exception as e:
            plots["production"] = f'{{"error": "Production plot failed: {str(e)}"}}'

        try:
            fig_press = plot_pressure(df)
            plots["pressure"] = fig_press.to_json()
        except Exception as e:
            plots["pressure"] = f'{{"error": "Pressure plot failed: {str(e)}"}}'

        return KPIsResponse(kpis=kpis, plots=plots)

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