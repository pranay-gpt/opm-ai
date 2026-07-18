"""Post-processing module for OPM Flow simulation results."""

from opm_ai.postprocess.kpi import extract_kpis
from opm_ai.postprocess.plots import plot_production, plot_pressure, plot_cumulative, plot_watercut
from opm_ai.postprocess.resinsight_bridge import (
    is_resinsight_available,
    load_case,
    create_summary_plots,
    create_3d_snapshot,
    export_case_html,
    create_full_visualization_workflow,
)
from opm_ai.postprocess.summary import read_summary

__all__ = [
    "read_summary",
    "extract_kpis",
    "plot_production",
    "plot_pressure",
    "plot_cumulative",
    "plot_watercut",
    "is_resinsight_available",
    "load_case",
    "create_summary_plots",
    "create_3d_snapshot",
    "export_case_html",
    "create_full_visualization_workflow",
]