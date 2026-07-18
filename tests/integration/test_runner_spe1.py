"""Integration test: run SPE1 fixture through the runner."""
import pytest
from pathlib import Path
from opm_ai.runner.models import SimulationJob
from opm_ai.runner.runner import run_simulation
from opm_ai.postprocess.summary import read_summary
from opm_ai.postprocess.kpi import extract_kpis


@pytest.mark.integration
@pytest.mark.slow
def test_run_spe1_fixture(tmp_path):
    """Run SPE1CASE1.DATA and verify KPIs."""
    fixture_path = Path("/home/parallels/opm-ai/tests/fixtures/spe1/SPE1CASE1.DATA")
    assert fixture_path.exists(), "SPE1 fixture not found"

    job = SimulationJob(
        deck_path=fixture_path,
        output_dir=tmp_path / "spe1_output",
        timeout=120,
    )

    result = run_simulation(job)

    assert result.success, f"Flow failed: {result.crash_report}"
    assert result.output_dir is not None
    assert result.output_dir.exists()

    # Read summary
    df = read_summary(result.output_dir)
    assert df is not None, "Failed to read summary"
    assert len(df) > 0, "Empty summary data"
    assert "TIME" in df.columns

    # SPE1 has well-level data, check for PROD well
    assert any("WOPT:PROD" in col for col in df.columns), "No WOPT:PROD column"

    # Extract KPIs
    kpis = extract_kpis(df)
    assert "days" in kpis
    assert kpis["days"] > 0

    # Check for available KPIs (SPE1 may not have all field totals)
    assert len(kpis) > 1, "No KPIs extracted"
