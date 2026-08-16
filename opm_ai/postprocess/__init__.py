"""Post-processing module for OPM Flow simulation results."""

from opm_ai.postprocess.categorizer import CategorizedVectors, categorize
from opm_ai.postprocess.kpi import extract_kpis
from opm_ai.postprocess.plots import plot_production, plot_pressure, plot_cumulative, plot_watercut
from opm_ai.postprocess.resinsight_bridge import (
    is_resinsight_available,
    export_snapshots,
    launch_resinsight,
)
from opm_ai.postprocess.summary import read_summary

__all__ = [
    "read_summary",
    "extract_kpis",
    "categorize",
    "CategorizedVectors",
    "plot_production",
    "plot_pressure",
    "plot_cumulative",
    "plot_watercut",
    "is_resinsight_available",
    "export_snapshots",
    "launch_resinsight",
]