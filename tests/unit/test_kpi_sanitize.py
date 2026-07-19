"""Regression test for NaN sanitization in KPI extraction."""

import json
import math

import pandas as pd
import pytest

from opm_ai.postprocess.kpi import extract_kpis


def test_extract_kpis_no_nan_values():
    """
    Regression test: KPIs with zero oil/water production should not contain float NaN.

    Scenario: A DataFrame with TIME, FOPR=0, FWPR=0, WOPR:P1=0, WWPR:P1=0
    This causes division by zero in watercut/GOR calculations which produces NaN.
    """
    # DataFrame with zero production rates (causes NaN in watercut/GOR)
    df = pd.DataFrame({
        "TIME": [1.0, 2.0],
        "FOPR": [0.0, 0.0],
        "FWPR": [0.0, 0.0],
        "FGPR": [0.0, 0.0],
        "WOPR:P1": [0.0, 0.0],
        "WWPR:P1": [0.0, 0.0],
        "WGPR:P1": [0.0, 0.0],
        "WBHP:P1": [3000.0, 2900.0],
    })

    kpis = extract_kpis(df)

    # Assert no value in the result dict is a float NaN
    nan_values = [(k, v) for k, v in kpis.items() if isinstance(v, float) and math.isnan(v)]
    assert not nan_values, f"Found NaN values in KPIs: {nan_values}"

    # Also verify JSON serialization with allow_nan=False works
    json.dumps(kpis, allow_nan=False)


def test_extract_kpis_no_inf_values():
    """Regression test: KPIs should not contain float infinity values."""
    df = pd.DataFrame({
        "TIME": [1.0, 2.0],
        "FOPR": [0.0, 0.0],
        "FWPR": [100.0, 100.0],  # Water production but no oil -> infinite watercut
        "WOPR:P1": [0.0, 0.0],
        "WWPR:P1": [100.0, 100.0],
        "WBHP:P1": [3000.0, 2900.0],
    })

    kpis = extract_kpis(df)

    # Assert no value is infinity
    inf_values = [(k, v) for k, v in kpis.items() if isinstance(v, float) and math.isinf(v)]
    assert not inf_values, f"Found infinite values in KPIs: {inf_values}"

    # JSON serialization should work
    json.dumps(kpis, allow_nan=False)


def test_extract_kpis_water_breakthrough_none_when_never():
    """water_breakthrough_day should be None (not NaN) when watercut never exceeds 1%."""
    df = pd.DataFrame({
        "TIME": [1.0, 2.0, 3.0],
        "FOPR": [100.0, 100.0, 100.0],
        "FWPR": [0.0, 0.0, 0.0],  # No water production ever
        "FOPT": [100.0, 200.0, 300.0],
    })

    kpis = extract_kpis(df)

    # Should be None, not NaN
    assert kpis.get("water_breakthrough_day") is None

    # And max_watercut should be 0.0 (not NaN)
    assert kpis.get("max_watercut") == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])