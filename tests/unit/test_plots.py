"""Test plotting functions."""
import pytest
import pandas as pd
from opm_ai.postprocess.plots import plot_production, plot_pressure


def test_plot_production():
    """Test production plotting."""
    df = pd.DataFrame({
        'TIME': [0, 100, 200],
        'FOPR': [100, 90, 80],
        'FWPR': [0, 10, 20],
        'FGPR': [50, 45, 40]
    })

    fig = plot_production(df)
    assert fig is not None
    assert len(fig.data) == 3  # Three traces


def test_plot_pressure():
    """Test pressure plotting."""
    df = pd.DataFrame({
        'TIME': [0, 100, 200],
        'WBHP:PROD': [250, 200, 150],
        'WBHP:INJ': [300, 310, 320]
    })

    fig = plot_pressure(df)
    assert fig is not None
    assert len(fig.data) == 2  # Two wells


def test_plot_empty_dataframe():
    """Test plotting with empty DataFrame."""
    df = pd.DataFrame()

    fig = plot_production(df)
    assert fig is not None
    assert len(fig.data) == 0
