"""opm_ai.postprocess — Part 5: Post-Processing & ResInsight Bridge.

Public API
----------
analyze_result(result)          -> PostProcessResult
open_in_resinsight(result, ...) -> bool
"""
from .models import (
    PostProcessResult,
    KPISet,
    SummaryFrame,
    PlotArtifact,
)
from .kpi_extractor import extract_kpis
from .plot_engine import generate_plots
from .resinsight_bridge import open_in_resinsight


def analyze_result(
    result,
    output_dir=None,
    generate_static_plots: bool = True,
    launch_resinsight: bool = False,
) -> "PostProcessResult":
    """Full post-processing pipeline for a completed SimulationResult."""
    from pathlib import Path

    if not result.succeeded:
        return PostProcessResult(
            simulation_result=result,
            kpis=KPISet.empty(),
            summary_frame=SummaryFrame.empty(),
            plots=[],
            resinsight_launched=False,
            error="Simulation did not succeed — no post-processing performed.",
        )

    out = Path(output_dir) if output_dir else result.job.output_dir or result.job.deck_path.parent
    out.mkdir(parents=True, exist_ok=True)

    summary_frame = _load_summary(result)
    kpis = extract_kpis(summary_frame)

    plots = []
    if generate_static_plots and not summary_frame.is_empty:
        plots = generate_plots(summary_frame, kpis, out)

    resinsight_ok = False
    if launch_resinsight:
        resinsight_ok = open_in_resinsight(result)

    return PostProcessResult(
        simulation_result=result,
        kpis=kpis,
        summary_frame=summary_frame,
        plots=plots,
        resinsight_launched=resinsight_ok,
    )


def _load_summary(result) -> "SummaryFrame":
    from .kpi_extractor import load_summary_ecl2df, load_summary_fallback
    if result.summary_file is None:
        return SummaryFrame.empty()
    try:
        return load_summary_ecl2df(result.summary_file)
    except Exception:
        pass
    try:
        return load_summary_fallback(result.summary_file)
    except Exception:
        return SummaryFrame.empty()


__all__ = [
    "analyze_result",
    "open_in_resinsight",
    "PostProcessResult",
    "KPISet",
    "SummaryFrame",
    "PlotArtifact",
    "extract_kpis",
    "generate_plots",
]
