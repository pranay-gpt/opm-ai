"""Shared job helpers.

Centralises small conversions that used to live inline at every route
callsite (F6.5/F6.6 audit fix). Kept as a separate module from
opm_ai.api.job_store (which owns persistence) so the helper layer
stays pure and is easy to test in isolation.
"""

from __future__ import annotations

from pathlib import Path

from opm_ai.api.schemas import JobStatus

__all__ = ["job_output_dir"]


def job_output_dir(job: JobStatus) -> Path:
    """Return a completed job's output directory as a ``pathlib.Path``.

    The job store stores ``output_dir`` as a string (it goes through
    ``model_dump(mode="json")`` when persisted and crosses the
    FastAPI wire format). Every route that reads summary files,
    exports snapshots, or finds the case file used to repeat
    ``Path(job.result.output_dir)`` inline — four callsites across
    ``opm_ai/api/routes/results.py`` and ``opm_ai/api/routes/chat.py``
    (F6.5/F6.6 audit).

    Raises ``ValueError`` if the job has no result yet (the routes
    guard on ``job.result is None`` before calling, so a missing
    result is always a programmer error here).
    """
    if job.result is None:
        raise ValueError(
            f"job_output_dir: job {job.job_id!r} has no result yet "
            f"(status={job.status!r})"
        )
    return Path(job.result.output_dir)
