"""Unit tests for opm_ai.postprocess.resample."""
import numpy as np
import pandas as pd
import pytest

from opm_ai.postprocess.resample import resample_summary


def _dt_df(start: str, days: int, **cols: list[float]) -> pd.DataFrame:
    """Build a DataFrame with a DatetimeIndex TIME column starting at start."""
    n = max(len(v) for v in cols.values())
    index = pd.date_range(start, periods=n, freq=f"{days}D") if n > 1 else pd.DatetimeIndex([pd.Timestamp(start)])
    return pd.DataFrame({"TIME": index, **cols})


def _step_df(steps: list[int], **cols: list[float]) -> pd.DataFrame:
    """Build a DataFrame with integer step TIME column (no datetime)."""
    return pd.DataFrame({"TIME": steps, **cols})


# ── Native ──────────────────────────────────────────────────────────────


def test_native_is_identity():
    df = _dt_df("2020-01-01", 1, FOPR=[100.0, 90.0, 80.0])
    out = resample_summary(df, "native")
    assert len(out) == 3
    assert list(out["FOPR"]) == [100.0, 90.0, 80.0]


def test_native_does_not_mutate_input():
    df = _dt_df("2020-01-01", 1, FOPR=[100.0])
    resample_summary(df, "native")
    assert list(df["FOPR"]) == [100.0]


# ── Datetime monthly ────────────────────────────────────────────────────


def test_monthly_rate_uses_mean():
    # 30 days of constant 100 STB/d -> mean = 100, one bucket
    df = _dt_df("2020-01-01", 1, FOPR=[100.0] * 30)
    out = resample_summary(df, "monthly")
    assert len(out) == 1
    assert out["FOPR"].iloc[0] == pytest.approx(100.0)


def test_monthly_cumulative_uses_last():
    # FOPT increases linearly from 0 to 2900 over 30 days -> last value = 2900
    df = _dt_df("2020-01-01", 1, FOPT=[float(i) for i in range(30)])
    out = resample_summary(df, "monthly")
    assert out["FOPT"].iloc[0] == pytest.approx(29.0)


# ── Datetime yearly ─────────────────────────────────────────────────────


def test_yearly_pressure_uses_mean():
    # 365 days of 3000 psia -> mean = 3000
    df = _dt_df("2020-01-01", 1, FPR=[3000.0] * 365)
    out = resample_summary(df, "yearly")
    assert len(out) == 1
    assert out["FPR"].iloc[0] == pytest.approx(3000.0)


# ── Step-index fallback ────────────────────────────────────────────────


def test_step_index_fallback_monthly():
    # Integer TIME that doesn't parse as datetime -> step-based bucketing
    # days_per_bucket=30, so steps 0..89 -> 3 monthly buckets
    df = _step_df(list(range(90)), FOPR=[100.0] * 90)
    out = resample_summary(df, "monthly")
    assert len(out) == 3
    assert pytest.approx(100.0) == out["FOPR"].values


# ── Bucket handling ─────────────────────────────────────────────────────


def test_empty_bucket_dropped():
    # 10 days in January, then a gap of 100 days, then 10 days in May
    df = _dt_df("2020-01-01", 1, FOPR=[100.0] * 10 + [np.nan] * 100 + [200.0] * 10)
    out = resample_summary(df, "monthly")
    # Two non-empty months (Jan and May); the NaN-only months should be dropped
    assert len(out) == 2
    assert out["FOPR"].iloc[0] == pytest.approx(100.0)
    assert out["FOPR"].iloc[1] == pytest.approx(200.0)


def test_mixed_suffixes_in_one_frame():
    # FOPR (rate) and FOPT (cumulative) in the same DataFrame
    df = _dt_df("2020-01-01", 1, FOPR=[100.0] * 60, FOPT=[float(i * 10) for i in range(60)])
    out = resample_summary(df, "monthly")
    assert len(out) == 2  # Jan, Feb
    # January FOPR mean = 100
    assert out["FOPR"].iloc[0] == pytest.approx(100.0)
    # January FOPT last = day 30 * 10 = 300
    assert out["FOPT"].iloc[0] == pytest.approx(300.0)
    # February FOPT last = day 59 * 10 = 590
    assert out["FOPT"].iloc[1] == pytest.approx(590.0)


def test_unknown_freq_raises():
    df = _dt_df("2020-01-01", 1, FOPR=[100.0])
    with pytest.raises(ValueError, match="Unknown freq"):
        resample_summary(df, "daily")