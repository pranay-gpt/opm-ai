"""Results route: GET /api/results/{job_id} -> KPIs + plots"""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from opm_ai.api.schemas import KPIsResponse
from opm_ai.api.job_store import get_job
from opm_ai.postprocess.summary import read_summary
from opm_ai.postprocess.kpi import extract_kpis
from opm_ai.postprocess.plots import plot_production, plot_pressure

router = APIRouter()


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