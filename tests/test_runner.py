# tests/test_runner.py
"""
Integration + unit tests for opm_ai.runner.

Run with:  python -m pytest tests/test_runner.py -v

Note: test_spe1_runs_successfully requires:
  1. OPM Flow installed  (sudo apt-get install libopm-simulators-bin)
  2. opm-tests submodule (git submodule update --init --recursive)
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from opm_ai.runner.models import SimulationJob, SimulationResult, SimulationStatus, CrashReport
from opm_ai.runner.runner import run_simulation, FLOW_BINARY

SPE1_DECK = Path("tests/fixtures/spe1/SPE1CASE1.DATA")


@pytest.mark.skipif(
    not FLOW_BINARY.exists(),
    reason="OPM Flow not installed — skipping integration test"
)
@pytest.mark.skipif(
    not SPE1_DECK.exists(),
    reason="opm-tests submodule not initialised — run: git submodule update --init"
)
def test_spe1_runs_successfully(tmp_path):
    """SPE1 must complete successfully and produce a .SMSPEC output file."""
    job = SimulationJob(
        deck_path=SPE1_DECK.resolve(),
        output_dir=tmp_path,
        timeout_seconds=120,
    )
    result = run_simulation(job)

    assert result.succeeded, (
        f"SPE1 simulation failed.\nErrors: {[e.message for e in result.errors]}"
    )
    assert result.summary_file is not None
    assert result.summary_file.exists(), "No .SMSPEC file produced"
    assert result.elapsed_seconds > 0


def test_missing_deck_returns_failed_result(tmp_path):
    """Runner must never raise — missing deck returns a FAILED result."""
    job = SimulationJob(
        deck_path=tmp_path / "nonexistent.DATA",
        output_dir=tmp_path,
    )
    result = run_simulation(job)

    assert result.status == SimulationStatus.FAILED
    assert len(result.errors) == 1
    assert "not found" in result.errors[0].message.lower()


def test_simulation_result_properties():
    """SimulationResult helper properties work correctly."""
    result = SimulationResult(
        job=MagicMock(),
        status=SimulationStatus.FAILED,
        elapsed_seconds=1.0,
        crash_reports=[
            CrashReport(severity="ERROR",   message="bad keyword"),
            CrashReport(severity="WARNING", message="suspicious value"),
        ]
    )
    assert not result.succeeded
    assert len(result.errors) == 1
    assert len(result.warnings) == 1
