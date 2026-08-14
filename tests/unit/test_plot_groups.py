"""Unit tests for opm_ai.postprocess.plot_groups."""
import pandas as pd
import plotly.graph_objects as go
import pytest

from opm_ai.postprocess.plot_groups import (
    plot_field_cumulative,
    plot_field_derived,
    plot_field_rates,
    plot_group,
    plot_well_cumulative,
    plot_well_injection,
    plot_well_rates,
)


def _df(**cols: dict[str, list[float]]) -> pd.DataFrame:
    n = max(len(v) for v in cols.values())
    return pd.DataFrame({"TIME": list(range(n)), **cols})


# ── Field groups ────────────────────────────────────────────────────────


def test_plot_field_rates_one_trace_per_vector():
    df = _df(FOPR=[100.0, 90.0], FWPR=[0.0, 5.0])
    fig = plot_field_rates(df)
    assert isinstance(fig, go.Figure)
    names = [trace.name for trace in fig.data]
    assert any("FOPR" in n for n in names)
    assert any("FWPR" in n for n in names)


def test_plot_field_rates_filter_by_vectors():
    df = _df(FOPR=[100.0], FWPR=[5.0], FGPR=[10.0])
    fig = plot_field_rates(df, vectors=["FOPR"])
    assert len(fig.data) == 1
    assert "FOPR" in fig.data[0].name


def test_plot_field_cumulative_has_traces():
    df = _df(FOPT=[1000.0, 2000.0], FWPT=[50.0, 100.0])
    fig = plot_field_cumulative(df)
    assert len(fig.data) == 2


def test_plot_field_derived_watercut():
    df = _df(FOPR=[100.0, 50.0], FWPR=[0.0, 50.0])
    fig = plot_field_derived(df, vectors=["FWCT"])
    assert len(fig.data) == 1
    # Watercut at t=1 should be 50 / (50+50) = 0.5 = 50%
    y = list(fig.data[0].y)
    assert y[0] == pytest.approx(0.0) or y[0] == pytest.approx(0.0, abs=1e-9)
    assert y[1] == pytest.approx(50.0)


# ── Well groups ─────────────────────────────────────────────────────────


def test_plot_well_rates_one_trace_per_well_per_vector():
    df = _df(**{"WOPR:PROD1": [50.0, 40.0], "WBHP:PROD1": [3000.0, 2900.0]})
    fig = plot_well_rates(df, wells=["PROD1"])
    assert len(fig.data) == 2


def test_plot_well_rates_filters_wells():
    df = _df(**{"WOPR:PROD1": [50.0], "WOPR:PROD2": [40.0]})
    fig = plot_well_rates(df, wells=["PROD1"], vectors=["WOPR"])
    assert len(fig.data) == 1
    assert "PROD1" in fig.data[0].name


def test_plot_well_rates_water_rate_sanitized():
    # FWPR-style negative zero: -0.0 should be clipped to 0
    df = _df(
        **{
            "WOPR:PROD1": [50.0, 50.0],
            "WWPR:PROD1": [-0.0, 5.0],
        }
    )
    fig = plot_well_rates(df, wells=["PROD1"])
    wwpr_trace = next(t for t in fig.data if "WWPR" in t.name)
    assert all(v >= 0 for v in wwpr_trace.y)


def test_plot_well_cumulative_filters():
    df = _df(
        **{"WOPT:PROD1": [1000.0, 1500.0], "WWPT:PROD1": [50.0, 60.0]}
    )
    fig = plot_well_cumulative(df, wells=["PROD1"], vectors=["WOPT"])
    assert len(fig.data) == 1


def test_plot_well_injection_filters():
    df = _df(**{"WGIR:GAS1": [10.0, 12.0], "WWIR:WAT1": [50.0, 55.0]})
    fig = plot_well_injection(df, wells=["GAS1", "WAT1"])
    assert len(fig.data) == 2


# ── Edge cases ──────────────────────────────────────────────────────────


def test_empty_dataframe_returns_empty_figure():
    df = pd.DataFrame(columns=["TIME"])
    fig = plot_field_rates(df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_missing_vectors_skipped():
    df = _df(FOPR=[100.0])  # FWPR not present
    fig = plot_field_rates(df)
    assert len(fig.data) == 1


def test_plot_group_dispatch():
    df = _df(FOPR=[100.0])
    fig = plot_group("field_rates", df, wells=[], vectors=None)
    assert len(fig.data) == 1


def test_plot_group_unknown_raises():
    df = _df(FOPR=[100.0])
    with pytest.raises(ValueError, match="Unknown group"):
        plot_group("nonsense", df, wells=[], vectors=None)


def test_log_scale_kwarg_applied():
    df = _df(FOPR=[100.0, 10.0])
    fig = plot_field_rates(df, log_scale=True)
    assert fig.layout.yaxis.type == "log"


def test_single_timestep_no_error():
    df = _df(FOPR=[100.0])
    fig = plot_field_rates(df)
    assert len(fig.data) == 1


def test_helpers_share_layout_style():
    # Common visual contract: title, axes labelled, hovermode unified
    df = _df(FOPR=[100.0])
    fig = plot_field_rates(df)
    assert fig.layout.hovermode == "x unified"
    assert fig.layout.xaxis.title.text  # non-empty
    assert fig.layout.yaxis.title.text