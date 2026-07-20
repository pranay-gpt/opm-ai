"""Test plotting functions."""
import pytest
import pandas as pd
import numpy as np
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


def test_plot_production_with_well_traces():
    """Test production plotting with per-producer traces when no field totals."""
    df = pd.DataFrame({
        'TIME': [0, 100, 200],
        'WOPR:PROD1': [50, 45, 40],
        'WWPR:PROD1': [0, 5, 10],
        'WOPR:PROD2': [30, 28, 25],
        'WWPR:PROD2': [0, 3, 7],
    })

    fig = plot_production(df)
    assert fig is not None
    assert len(fig.data) == 4  # Two producers, oil + water each


def test_plot_production_field_and_well():
    """Test production plotting with both field and well data (field takes priority)."""
    df = pd.DataFrame({
        'TIME': [0, 100, 200],
        'FOPR': [100, 90, 80],
        'FWPR': [0, 10, 20],
        'WOPR:PROD1': [60, 55, 50],
        'WWPR:PROD1': [0, 5, 10],
    })

    fig = plot_production(df)
    assert fig is not None
    # Should only show field traces, not well traces (field takes priority)
    assert len(fig.data) == 2


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


def test_plot_production_watercut_negative_zero():
    """Test watercut computation handles -0.0 correctly."""
    df = pd.DataFrame({
        'TIME': [0, 100, 200],
        'FOPR': [100, 90, 80],
        'FWPR': [-0.0, -0.0, 10.0],  # Negative zeros
    })

    fig = plot_production(df)
    assert fig is not None
    assert len(fig.data) == 2  # FOPR and FWPR
    # FWPR values should be clipped to 0
    trace = fig.data[1]
    assert trace.y[0] == 0.0
    assert trace.y[1] == 0.0
    assert trace.y[2] == 10.0
