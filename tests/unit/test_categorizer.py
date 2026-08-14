"""Unit tests for opm_ai.postprocess.categorizer."""
import pandas as pd
import pytest

from opm_ai.postprocess.categorizer import (
    CategorizedVectors,
    categorize,
)


def _df(**cols: dict[str, list[float]]) -> pd.DataFrame:
    """Build a one-row-per-timestep DataFrame with TIME column."""
    n = max(len(v) for v in cols.values())
    data: dict[str, list] = {"TIME": list(range(n))}
    data.update(cols)
    return pd.DataFrame(data)


def test_empty_dataframe_returns_empty_categories():
    df = pd.DataFrame(columns=["TIME"])
    result = categorize(df)
    assert result["wells"] == []
    assert result["field_rates"] == []
    assert result["field_cumulative"] == []
    assert result["field_derived"] == []
    assert result["well_rates"] == {}
    assert result["well_cumulative"] == {}
    assert result["well_injection"] == {}


def test_only_field_rates():
    df = _df(FOPR=[100.0, 90.0], FWPR=[0.0, 5.0], FGPR=[10.0, 8.0])
    result = categorize(df)
    assert sorted(result["field_rates"]) == ["FGPR", "FOPR", "FWPR"]
    assert result["field_cumulative"] == []
    assert result["field_derived"] == []


def test_only_well_rates():
    df = _df(**{"WOPR:PROD1": [100.0, 50.0], "WBHP:PROD1": [3000.0, 2900.0]})
    result = categorize(df)
    assert result["wells"] == ["PROD1"]
    assert sorted(result["well_rates"]["PROD1"]) == ["WBHP", "WOPR"]
    assert result["well_cumulative"] == {}
    assert result["well_injection"] == {}


def test_mixed_field_and_well():
    df = _df(
        FOPR=[100.0],
        FOPT=[1000.0],
        **{"WOPR:PROD1": [50.0], "WBHP:PROD1": [3000.0]},
    )
    result = categorize(df)
    assert result["field_rates"] == ["FOPR"]
    assert result["field_cumulative"] == ["FOPT"]
    assert result["wells"] == ["PROD1"]
    assert sorted(result["well_rates"]["PROD1"]) == ["WBHP", "WOPR"]


def test_no_positive_producer_well_excluded():
    # WOPR is all zero — well is not a producer
    df = _df(**{"WOPR:DEAD": [0.0, 0.0], "WBHP:DEAD": [3000.0, 3000.0]})
    result = categorize(df)
    assert result["wells"] == ["DEAD"]  # appears in wells list
    assert result["well_rates"] == {}    # but no rates group (well isn't a producer)


def test_water_producer_recognized_without_oil():
    # WWPR positive, WOPR zero — pure water producer should still be categorized
    df = _df(
        **{
            "WOPR:WATER1": [0.0, 0.0],
            "WWPR:WATER1": [50.0, 60.0],
            "WBHP:WATER1": [3000.0, 2900.0],
        }
    )
    result = categorize(df)
    assert "WATER1" in result["wells"]
    assert sorted(result["well_rates"]["WATER1"]) == ["WBHP", "WWPR"]


def test_injector_recognized():
    df = _df(
        **{
            "WGIR:GAS1": [100.0, 90.0],
            "WGIT:GAS1": [1000.0, 1500.0],
            "WWIR:WAT1": [200.0, 180.0],
            "WWIT:WAT1": [5000.0, 6500.0],
        }
    )
    result = categorize(df)
    assert sorted(result["wells"]) == ["GAS1", "WAT1"]
    assert sorted(result["well_injection"]["GAS1"]) == ["WGIR", "WGIT"]
    assert sorted(result["well_injection"]["WAT1"]) == ["WWIR", "WWIT"]
    assert result["well_rates"] == {}


def test_mixed_producer_and_injector_well():
    # Well with both production and injection appears in both groups
    df = _df(
        **{
            "WOPR:DUAL": [50.0, 40.0],
            "WGIR:DUAL": [10.0, 12.0],
        }
    )
    result = categorize(df)
    assert "DUAL" in result["well_rates"]
    assert "DUAL" in result["well_injection"]
    assert "WOPR" in result["well_rates"]["DUAL"]
    assert "WGIR" in result["well_injection"]["DUAL"]


def test_rft_columns_ignored():
    # RFT files use CONDEPTH, CONPRES — not in any well keyword list
    df = _df(
        FOPR=[100.0],
        **{"CONDEPTH:W1": [8000.0], "CONPRES:W1": [3000.0]},
    )
    result = categorize(df)
    assert result["field_rates"] == ["FOPR"]
    # CONDEPTH/CONPRES are not in any well_* keyword list, so well is dropped
    assert result["well_rates"] == {}
    assert result["wells"] == []


def test_unknown_well_keyword_ignored():
    # WWELLFOO is not in any list — column passes through, well is not categorised
    df = _df(
        FOPR=[100.0],
        **{"WWELLFOO:PROD1": [42.0]},
    )
    result = categorize(df)
    assert result["field_rates"] == ["FOPR"]
    assert result["wells"] == []
    assert result["well_rates"] == {}