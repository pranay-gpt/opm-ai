"""Run route: POST /api/run (background job), GET /api/run/{job_id}"""

import asyncio
from fastapi import APIRouter, HTTPException
from pathlib import Path
from uuid import uuid4

from opm_ai.api.paths import validate_deck_path
from opm_ai.api.schemas import (
    RunRequest, JobStatus, SimulationResultDTO
)
from opm_ai.runner import run_simulation
from opm_ai.runner.models import SimulationJob
from opm_ai.api.job_store import (
    create_job, get_job, set_job_running, set_job_completed, set_job_failed
)

router = APIRouter()


@router.post("/run", response_model=JobStatus)
async def run_simulation_endpoint(request: RunRequest) -> JobStatus:
    """
    Start a simulation as a background job.

    Returns job_id immediately. Poll GET /api/run/{job_id} for status.
    """
    try:
        deck_path = validate_deck_path(request.deck_path)
        if not deck_path.exists():
            raise HTTPException(status_code=404, detail=f"Deck not found: {deck_path}")

        job_id = str(uuid4())
        output_dir = deck_path.parent / f"output_{job_id[:8]}"

        # Create pending job (may raise ValueError if store at capacity)
        create_job(job_id)

        # Spawn background task
        asyncio.create_task(run_job_background(job_id, deck_path, output_dir, request.timeout))

        return JobStatus(job_id=job_id, status="pending")
    except HTTPException:
        raise
    except ValueError as e:
        # Check if it's a capacity error
        if "at capacity" in str(e) or "cannot accept new jobs" in str(e):
            raise HTTPException(status_code=429, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_job_background(
    job_id: str,
    deck_path: Path,
    output_dir: Path,
    timeout: int
) -> None:
    """Background task to run simulation and update job store."""
    set_job_running(job_id)

    try:
        job = SimulationJob(
            deck_path=deck_path,
            output_dir=output_dir,
            timeout=timeout,
        )

        # Run simulation in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_simulation, job)

        if result.success:
            # F4.2 audit fix: classmethod on the DTO collapses the 12-line
            # inline conversion that used to live here. The runner model
            # is the source of truth; the DTO is a stringified view of it
            # for JSON serialization and job-store storage.
            set_job_completed(job_id, SimulationResultDTO.from_runner(result))
        else:
            set_job_completed(job_id, SimulationResultDTO.from_runner(result))

    except Exception as e:
        set_job_failed(job_id, str(e))


@router.get("/run/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str) -> JobStatus:
    """Get the status of a simulation job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobStatus(
        job_id=job.job_id,
        status=job.status,
        result=job.result,
        error=job.error,
    )