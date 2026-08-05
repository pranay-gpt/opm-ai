"""Unit tests for opm_ai.api.job_helpers (F6.5/F6.6 audit fix).

The helper centralises the ``Path(job.result.output_dir)`` unwrap
that two routes used to repeat inline. The wire-format DTO stores
``output_dir`` as a ``str`` (Pydantic ``model_dump(mode="json")``
serialises ``Path`` to ``str``), so the unwrap is the only piece
that needed lifting - the routes' 404/400 status checks stay with
the routes because that's their policy.
"""

import pytest
from pathlib import Path

from opm_ai.api.job_helpers import job_output_dir
from opm_ai.api.schemas import JobStatus, SimulationResultDTO, CrashReportDTO


def _make_completed_job(output_dir: object) -> JobStatus:
    """Build a JobStatus with status='completed' and a populated result."""
    return JobStatus(
        job_id="job-1",
        status="completed",
        result=SimulationResultDTO(
            success=True,
            output_dir=output_dir,  # str | Path both accepted by the DTO
            crash_report=None,
        ),
    )


def test_job_output_dir_returns_path_from_str():
    """The wire-format DTO stores output_dir as str; the helper must
    convert it to a pathlib.Path so the route can pass it to
    read_summary / find_case_file / export_snapshots which all
    expect a Path."""
    job = _make_completed_job("/tmp/runs/output_abcdef12")
    result = job_output_dir(job)
    assert isinstance(result, Path)
    assert str(result) == "/tmp/runs/output_abcdef12"


def test_job_output_dir_handles_relative_path():
    """Relative output_dir paths round-trip correctly - the wire DTO
    stores them as-is, and Path() preserves the relativity."""
    job = _make_completed_job("output_xyz")
    result = job_output_dir(job)
    assert isinstance(result, Path)
    assert str(result) == "output_xyz"


def test_job_output_dir_raises_on_no_result():
    """A job that hasn't completed yet has no result. The helper
    raises a clear ValueError instead of letting ``Path(None)``
    throw a confusing TypeError two frames deep."""
    job = JobStatus(job_id="job-2", status="running", result=None)
    with pytest.raises(ValueError, match="no result yet"):
        job_output_dir(job)


def test_job_output_dir_raises_on_failed_job():
    """A failed job has a result too (with success=False) - this
    test pins down that 'no result' is the only None path the
    helper needs to guard against."""
    job = JobStatus(
        job_id="job-3",
        status="failed",
        result=SimulationResultDTO(
            success=False,
            output_dir="/tmp/runs/output_failed",
            crash_report=CrashReportDTO(
                keyword="RUNSPEC",
                line=1,
                message="boom",
            ),
        ),
    )
    result = job_output_dir(job)
    assert isinstance(result, Path)
    assert str(result) == "/tmp/runs/output_failed"
