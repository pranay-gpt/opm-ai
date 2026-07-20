"""In-memory job store for async simulation runs with bounded eviction."""

import uuid
from collections import OrderedDict
from threading import Lock
from typing import Any, Optional

from opm_ai.api.schemas import JobStatus, SimulationResultDTO
from opm_ai.settings import settings


class JobStore:
    """Thread-safe bounded job store with LRU eviction of completed jobs."""

    def __init__(self, max_entries: Optional[int] = None):
        self._jobs: OrderedDict[str, JobStatus] = OrderedDict()
        self._lock = Lock()
        self._max_entries = max_entries if max_entries is not None else settings.job_store_max_entries

    def _evict_if_needed(self) -> None:
        """Evict oldest completed jobs if over capacity.

        Never evicts running or pending jobs. If all jobs are running/pending
        and capacity is reached, raises ValueError.
        """
        while len(self._jobs) >= self._max_entries:
            # Find oldest completed/failed job
            evicted = False
            for job_id, job in self._jobs.items():
                if job.status in ("completed", "failed"):
                    del self._jobs[job_id]
                    evicted = True
                    break

            if not evicted:
                # All jobs are running/pending - cannot evict
                raise ValueError(
                    f"Job store at capacity ({self._max_entries}) with all jobs running/pending. "
                    f"Cannot accept new jobs. Please wait for running jobs to complete."
                )

    def create_job(self, job_id: Optional[str] = None) -> str:
        """Create a new job and return its ID."""
        with self._lock:
            self._evict_if_needed()

            if job_id is None:
                job_id = str(uuid.uuid4())
            job = JobStatus(job_id=job_id, status="pending")
            self._jobs[job_id] = job
            return job_id

    def get_job(self, job_id: str) -> Optional[JobStatus]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs: Any) -> Optional[JobStatus]:
        """Update a job's fields."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                for key, value in kwargs.items():
                    setattr(job, key, value)
            return job

    def set_job_running(self, job_id: str) -> Optional[JobStatus]:
        """Mark job as running."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "running"
            return job

    def set_job_completed(self, job_id: str, result: SimulationResultDTO) -> Optional[JobStatus]:
        """Mark job as completed with result."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "completed"
                job.result = result
            return job

    def set_job_failed(self, job_id: str, error: str) -> Optional[JobStatus]:
        """Mark job as failed with error."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.error = error
            return job

    def get_all_jobs(self) -> dict[str, JobStatus]:
        """Get all jobs (for debugging)."""
        with self._lock:
            return dict(self._jobs)

    def __len__(self) -> int:
        with self._lock:
            return len(self._jobs)


# Global job store instance
_job_store = JobStore()


def create_job(job_id: Optional[str] = None) -> str:
    """Create a new job and return its ID."""
    return _job_store.create_job(job_id)


def get_job(job_id: str) -> Optional[JobStatus]:
    """Get a job by ID."""
    return _job_store.get_job(job_id)


def update_job(job_id: str, **kwargs: Any) -> Optional[JobStatus]:
    """Update a job's fields."""
    return _job_store.update_job(job_id, **kwargs)


def set_job_running(job_id: str) -> Optional[JobStatus]:
    """Mark job as running."""
    return _job_store.set_job_running(job_id)


def set_job_completed(job_id: str, result: SimulationResultDTO) -> Optional[JobStatus]:
    """Mark job as completed with result."""
    return _job_store.set_job_completed(job_id, result)


def set_job_failed(job_id: str, error: str) -> Optional[JobStatus]:
    """Mark job as failed with error."""
    return _job_store.set_job_failed(job_id, error)


def get_all_jobs() -> dict[str, JobStatus]:
    """Get all jobs (for debugging)."""
    return _job_store.get_all_jobs()