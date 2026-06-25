"""Part 5 tests — opm_postprocess.

All tests work without OPM Flow, ResInsight, or ecl2df installed.
They operate entirely on synthetic in-memory data.
"""
from __future__ import annotations
import datetime
from pathlib import Path
import pytest


def make_synthetic_sf(n=50, has_foip=True, has_wwct=True):
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        pytest.skip("pandas/numpy not installed")

    from opm_ai.postprocess.models import SummaryFrame

    start = datetime.datetime(2020, 1, 1)
    dates = pd.date_range(start, periods=n, freq="ME")
    t = np.linspace(0, 1, n)

    data = {
        "FOPR": 1000 * np.exp(-2 * t),
        "FWPR": 500 * t,
        "FGPR": 200 * np.exp(-t),
        "FWIR": np.full(n, 800.0),
        "FWIT": 800 * np.arange(n) * 30.5,
        "FOPT": 1000 * (1 - np.exp(-2 * t)) * 180,
        "FWPT": 500 * t * 180,
        "FPR": 250 - 50 * t,
        "NTS": np.arange(n, dtype=float),
    }
    if has_wwct:
        data["WWCT:PROD1"] = np.clip(t - 0.3, 0, 1)
    if has_foip:
        data["FOIP"] = np.full(n, 500_000.0)

    df = pd.DataFrame(data, index=pd.DatetimeIndex(dates))
    df.index.name = "DATE"

    return SummaryFrame(df=df, dates=list(dates), vectors=list(df.columns), case_name="SYNTH01")


# ── SummaryFrame ────────────────────────────────────────────────────────────────

def test_summary_frame_empty_classmethod():
    from opm_ai.postprocess.models import SummaryFrame
    sf = SummaryFrame.empty()           # classmethod — no longer clashes
    assert sf.df is None
    assert sf.vectors == []


def test_summary_frame_is_empty_property():
    from opm_ai.postprocess.models import SummaryFrame
    sf = SummaryFrame.empty()
    assert sf.is_empty is True


def test_summary_frame_not_empty_with_data():
    sf = make_synthetic_sf()
    assert sf.df is not None
    assert len(sf.vectors) > 0
    assert sf.is_empty is False


# ── KPISet ───────────────────────────────────────────────────────────────────

def test_kpiset_empty():
    from opm_ai.postprocess.models import KPISet
    k = KPISet.empty()
    assert k.fopt is None
    assert k.recovery_factor is None
    assert k.as_dict() == {}


def test_kpiset_narrative_bullets_empty():
    from opm_ai.postprocess.models import KPISet
    assert KPISet.empty().narrative_bullets() == []


# ── KPI extraction ───────────────────────────────────────────────────────────

def test_extract_kpis_from_synthetic():
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    sf = make_synthetic_sf()
    kpis = extract_kpis(sf)
    assert kpis.fopt is not None and kpis.fopt > 0
    assert kpis.fwit is not None and kpis.fwit > 0
    assert kpis.initial_fpr is not None and kpis.final_fpr is not None
    assert kpis.initial_fpr > kpis.final_fpr
    assert kpis.pressure_drop is not None and kpis.pressure_drop > 0


def test_recovery_factor_computed():
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    sf = make_synthetic_sf(has_foip=True)
    kpis = extract_kpis(sf)
    assert kpis.recovery_factor is not None
    assert 0 < kpis.recovery_factor < 1


def test_no_foip_means_no_recovery_factor():
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    sf = make_synthetic_sf(has_foip=False)
    kpis = extract_kpis(sf)
    assert kpis.recovery_factor is None


def test_water_breakthrough_detected():
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    sf = make_synthetic_sf(has_wwct=True)
    kpis = extract_kpis(sf)
    assert kpis.wct_breakthrough_date is not None
    assert kpis.wct_breakthrough_years is not None and kpis.wct_breakthrough_years > 0


def test_no_wwct_no_breakthrough():
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        pytest.skip()
    from opm_ai.postprocess.models import SummaryFrame
    dates = pd.date_range(datetime.datetime(2020, 1, 1), periods=10, freq="ME")
    df = pd.DataFrame({"FOPT": np.linspace(0, 1000, 10)}, index=dates)
    sf = SummaryFrame(df=df, dates=list(dates), vectors=list(df.columns))
    kpis = extract_kpis(sf)
    assert kpis.wct_breakthrough_date is None


def test_extract_kpis_empty_sf():
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    from opm_ai.postprocess.models import SummaryFrame
    kpis = extract_kpis(SummaryFrame.empty())
    assert kpis.fopt is None


def test_kpis_narrative_bullets_populated():
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    sf = make_synthetic_sf()
    kpis = extract_kpis(sf)
    bullets = kpis.narrative_bullets()
    assert isinstance(bullets, list)
    assert len(bullets) >= 2
    assert any("oil" in b.lower() or "FOPT" in b for b in bullets)


def test_as_dict_only_non_none():
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    sf = make_synthetic_sf()
    kpis = extract_kpis(sf)
    d = kpis.as_dict()
    assert all(v is not None for v in d.values())
    assert isinstance(d, dict)


# ── Plot engine ──────────────────────────────────────────────────────────────

def test_generate_plots_returns_artifacts(tmp_path):
    from opm_ai.postprocess.plot_engine import generate_plots
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    sf = make_synthetic_sf()
    kpis = extract_kpis(sf)
    artifacts = generate_plots(sf, kpis, tmp_path)
    assert len(artifacts) >= 3
    for art in artifacts:
        assert art.png_path.exists(), f"PNG not written: {art.png_path}"


def test_generate_plots_empty_sf_returns_empty(tmp_path):
    from opm_ai.postprocess.plot_engine import generate_plots
    from opm_ai.postprocess.models import SummaryFrame, KPISet
    result = generate_plots(SummaryFrame.empty(), KPISet.empty(), tmp_path)
    assert result == []


def test_recovery_efficiency_plot_needs_foip(tmp_path):
    from opm_ai.postprocess.plot_engine import generate_plots
    from opm_ai.postprocess.kpi_extractor import extract_kpis
    sf = make_synthetic_sf(has_foip=False)
    kpis = extract_kpis(sf)
    artifacts = generate_plots(sf, kpis, tmp_path)
    names = [a.name for a in artifacts]
    assert "recovery_efficiency" not in names


# ── PostProcessResult ─────────────────────────────────────────────────────────

def test_postprocess_result_succeeded_flag():
    from opm_ai.postprocess.models import PostProcessResult, KPISet, SummaryFrame
    r = PostProcessResult(
        simulation_result=None,
        kpis=KPISet.empty(),
        summary_frame=SummaryFrame.empty(),
    )
    assert r.succeeded is True
    assert r.plot_paths() == []


def test_postprocess_result_with_error():
    from opm_ai.postprocess.models import PostProcessResult, KPISet, SummaryFrame
    r = PostProcessResult(
        simulation_result=None,
        kpis=KPISet.empty(),
        summary_frame=SummaryFrame.empty(),
        error="Simulation failed",
    )
    assert r.succeeded is False


# ── ResInsight bridge ────────────────────────────────────────────────────────────

def test_resinsight_bridge_importable():
    from opm_ai.postprocess import resinsight_bridge
    assert callable(resinsight_bridge.open_in_resinsight)


def test_resinsight_returns_false_without_rips():
    import sys
    rips_mod = sys.modules.get("rips")
    sys.modules["rips"] = None  # type: ignore
    try:
        # Re-import to pick up the mocked module
        import importlib
        import opm_ai.postprocess.resinsight_bridge as rb
        importlib.reload(rb)
        class _FakeResult:
            succeeded = True
            summary_file = None
            job = type("J", (), {"deck_path": Path("/tmp/fake.DATA"),
                                  "output_dir": None})()
        assert rb.open_in_resinsight(_FakeResult()) is False
    finally:
        if rips_mod is not None:
            sys.modules["rips"] = rips_mod
        else:
            sys.modules.pop("rips", None)


def test_resinsight_returns_false_on_failed_simulation():
    from opm_ai.postprocess.resinsight_bridge import open_in_resinsight
    class _FakeResult:
        succeeded = False
    assert open_in_resinsight(_FakeResult()) is False
