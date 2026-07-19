"""In-memory job store for async simulation runs."""

import uuid
from typing import Any
from opm_ai.api.schemas import JobStatus, SimulationResultDTO


_jobs: dict[str, JobStatus] = {}


def create_job(job_id: str | None = None) -> str:
    """Create a new job and return its ID."""
    if job_id is None:
        job_id = str(uuid.uuid4())
    job = JobStatus(job_id=job_id, status="pending")
    _jobs[job_id] = job
    return job_id


def get_job(job_id: str) -> JobStatus | None:
    """Get a job by ID."""
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs: Any) -> JobStatus | None:
    """Update a job's fields."""
    job = _jobs.get(job_id)
    if job:
        for key, value in kwargs.items():
            setattr(job, key, value)
    return job


def set_job_running(job_id: str) -> JobStatus | None:
    """Mark job as running."""
    return update_job(job_id, status="running")


def set_job_completed(job_id: str, result: SimulationResultDTO) -> JobStatus | None:
    """Mark job as completed with result."""
    return update_job(job_id, status="completed", result=result)


def set_job_failed(job_id: str, error: str) -> JobStatus | None:
    """Mark job as failed with error."""
    return update_job(job_id, status="failed", error=error)


def get_all_jobs() -> dict[str, JobStatus]:
    """Get all jobs (for debugging)."""
    return _jobs