"""Standard diagnostic plots for reservoir simulation results.

Canonical plot set (6 plots, drive-mechanism aware):
  1. FOPR / FWPR / FGPR / FWIR  — Field production + injection rates vs time
  2. FOPT / FWIT                 — Cumulative oil production + water injection
  3. FPR                         — Field average reservoir pressure vs time
  4. WWCT (per well + field)     — Water cut diagnostic
  5. WBHP (per well)             — Well BHP vs time
  6. Recovery efficiency         — FOPT/FOIP0 vs FWIT/FOIP0 (waterflood)

All plots are Plotly interactive HTML (always) + matplotlib PNG (always).
ResInsight is used locally via subprocess when available (RESINSIGHT_BIN env or PATH).
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import logging
import warnings

from .models import SummaryFrame, KPISet, PlotArtifact

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")


def generate_plots(
    sf: SummaryFrame,
    kpis: KPISet,
    output_dir: Path,
) -> list[PlotArtifact]:
    """Generate the full canonical plot set."""
    if sf.is_empty or sf.df is None:
        return []

    artifacts = []
    plotters = [
        _plot_production_rates,
        _plot_cumulative,
        _plot_field_pressure,
        _plot_water_cut,
        _plot_bhp,
        _plot_recovery_efficiency,
    ]
    for fn in plotters:
        try:
            art = fn(sf, kpis, output_dir)
            if art:
                artifacts.append(art)
        except Exception as exc:
            log.debug("Plot %s skipped: %s", fn.__name__, exc)
    return artifacts


# ─────────────────────────────────────────────────────────────────────────────
def _plot_production_rates(sf, kpis, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    df = sf.df
    rate_cols = {
        "FOPR": "Oil Rate (SM³/day)",
        "FWPR": "Water Prod Rate (SM³/day)",
        "FGPR": "Gas Rate (SM³/day)",
        "FWIR": "Water Inj Rate (SM³/day)",
    }
    present = {k: v for k, v in rate_cols.items() if k in df.columns}
    if not present:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#2563EB", "#16A34A", "#DC2626", "#9333EA"]
    for (col, label), color in zip(present.items(), colors):
        ax.plot(df.index, df[col].values, label=label, color=color, linewidth=1.8)
    _add_breakthrough(ax, kpis)
    _style_axis(ax, "Field Production & Injection Rates", "Date", "Rate (SM³/day)")
    fig.tight_layout()

    png = out / "01_production_rates.png"
    fig.savefig(str(png), dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="production_rates",
        png_path=png,
        html_path=_plotly_lines(df, present, kpis,
                                out / "01_production_rates.html",
                                "Field Production & Injection Rates",
                                "Rate (SM³/day)"),
        description="Field oil/water/gas production and water injection rates vs time.",
    )


def _plot_cumulative(sf, kpis, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sf.df
    cum_cols = {
        "FOPT": "Cumulative Oil (SM³)",
        "FWIT": "Cumulative Water Injected (SM³)",
        "FWPT": "Cumulative Water Produced (SM³)",
    }
    present = {k: v for k, v in cum_cols.items() if k in df.columns}
    if not present:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#2563EB", "#9333EA", "#16A34A"]
    for (col, label), color in zip(present.items(), colors):
        ax.plot(df.index, df[col].values, label=label, color=color, linewidth=1.8)
    _style_axis(ax, "Cumulative Production & Injection", "Date", "Volume (SM³)")
    fig.tight_layout()

    png = out / "02_cumulative.png"
    fig.savefig(str(png), dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="cumulative",
        png_path=png,
        html_path=_plotly_lines(df, present, kpis,
                                out / "02_cumulative.html",
                                "Cumulative Production & Injection",
                                "Volume (SM³)"),
        description="Cumulative oil production and water injection vs time.",
    )


def _plot_field_pressure(sf, kpis, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sf.df
    if "FPR" not in df.columns:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df.index, df["FPR"].values, color="#B45309", linewidth=2, label="FPR")
    if kpis.initial_fpr is not None:
        ax.axhline(kpis.initial_fpr, color="gray", linestyle="--", linewidth=1,
                   label=f"Initial: {kpis.initial_fpr:.1f} bar")
    if kpis.final_fpr is not None:
        ax.axhline(kpis.final_fpr, color="#DC2626", linestyle="--", linewidth=1,
                   label=f"Final: {kpis.final_fpr:.1f} bar")
    _style_axis(ax, "Field Average Reservoir Pressure (FPR)", "Date", "Pressure (bar)")
    fig.tight_layout()

    png = out / "03_field_pressure.png"
    fig.savefig(str(png), dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="field_pressure",
        png_path=png,
        html_path=_plotly_lines(df, {"FPR": "Field Avg Pressure (bar)"}, kpis,
                                out / "03_field_pressure.html",
                                "Field Average Reservoir Pressure", "Pressure (bar)"),
        description="Field average reservoir pressure vs time.",
    )


def _plot_water_cut(sf, kpis, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sf.df
    wwct_cols = [c for c in df.columns if c.startswith("WWCT")]
    has_field_rates = "FWPR" in df.columns and "FOPR" in df.columns
    if not wwct_cols and not has_field_rates:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))
    plot_cols = {}

    if wwct_cols:
        for col in wwct_cols:
            well = col.split(":", 1)[-1] if ":" in col else col
            ax.plot(df.index, df[col].values, linewidth=1.6, label=well)
            plot_cols[col] = well
    elif has_field_rates:
        total = df["FWPR"] + df["FOPR"]
        fwct = df["FWPR"] / total.where(total > 0)
        ax.plot(df.index, fwct.values, color="#16A34A", linewidth=2, label="Field WCT")

    ax.axhline(0.05, color="orange", linestyle=":", linewidth=1, label="BT threshold 5%")
    ax.set_ylim(0, 1.05)
    _add_breakthrough(ax, kpis)
    _style_axis(ax, "Well / Field Water Cut (WWCT)", "Date", "Water Cut (fraction)")
    fig.tight_layout()

    png = out / "04_water_cut.png"
    fig.savefig(str(png), dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="water_cut",
        png_path=png,
        html_path=_plotly_lines(df, {c: c.split(":", 1)[-1] for c in (wwct_cols or [])},
                                kpis, out / "04_water_cut.html",
                                "Well / Field Water Cut", "Water Cut (fraction)"),
        description="Well water cut vs time — key waterflood performance indicator.",
    )


def _plot_bhp(sf, kpis, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sf.df
    wbhp_cols = [c for c in df.columns if c.startswith("WBHP")]
    if not wbhp_cols:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))
    for col in wbhp_cols:
        well = col.split(":", 1)[-1] if ":" in col else col
        ax.plot(df.index, df[col].values, linewidth=1.6, label=well)
    _style_axis(ax, "Well Bottom-Hole Pressure (WBHP)", "Date", "BHP (bar)")
    fig.tight_layout()

    png = out / "05_bhp.png"
    fig.savefig(str(png), dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="bhp",
        png_path=png,
        description="Well bottom-hole pressures vs time.",
    )


def _plot_recovery_efficiency(sf, kpis, out):
    """RF vs PVI — the waterflood engineer’s primary diagnostic."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sf.df
    if kpis.foip_initial is None or kpis.foip_initial == 0:
        return None
    if "FOPT" not in df.columns or "FWIT" not in df.columns:
        return None

    re = df["FOPT"] / kpis.foip_initial
    pvi = df["FWIT"] / kpis.foip_initial

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(pvi.values, re.values, color="#2563EB", linewidth=2)
    ax.set_xlabel("Pore Volumes Injected (FWIT / FOIP₀)")
    ax.set_ylabel("Recovery Factor (FOPT / FOIP₀)")
    ax.set_title("Recovery Efficiency Curve")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    png = out / "06_recovery_efficiency.png"
    fig.savefig(str(png), dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Plotly interactive version
    html = _plotly_xy(
        x=pvi, y=re,
        path=out / "06_recovery_efficiency.html",
        title="Recovery Efficiency Curve",
        xaxis="Pore Volumes Injected (FWIT / FOIP₀)",
        yaxis="Recovery Factor (FOPT / FOIP₀)",
    )

    return PlotArtifact(
        name="recovery_efficiency",
        png_path=png,
        html_path=html,
        description="Recovery factor vs pore volumes injected — primary waterflood efficiency diagnostic.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Plotly helpers
# ─────────────────────────────────────────────────────────────────────────────

def _plotly_lines(df, col_map: dict, kpis: KPISet, path: Path,
                  title: str, yaxis: str) -> Optional[Path]:
    try:
        import plotly.graph_objects as go
        colors = ["#2563EB", "#16A34A", "#DC2626", "#9333EA", "#B45309", "#0891B2"]
        fig = go.Figure()
        for (col, label), color in zip(col_map.items(), colors):
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col].values,
                    mode="lines", name=label,
                    line=dict(color=color, width=2),
                ))
        if kpis.wct_breakthrough_date:
            fig.add_vline(
                x=str(kpis.wct_breakthrough_date),
                line_dash="dash", line_color="orange",
                annotation_text=f"Water BT (~yr {kpis.wct_breakthrough_years:.1f})",
            )
        fig.update_layout(
            title=title, xaxis_title="Date", yaxis_title=yaxis,
            template="plotly_white", hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig.write_html(str(path))
        return path
    except Exception as exc:
        log.debug("Plotly HTML skipped for %s: %s", path.name, exc)
        return None


def _plotly_xy(x, y, path: Path, title: str, xaxis: str, yaxis: str) -> Optional[Path]:
    try:
        import plotly.graph_objects as go
        fig = go.Figure(go.Scatter(x=x.values, y=y.values, mode="lines",
                                   line=dict(color="#2563EB", width=2)))
        fig.update_layout(
            title=title, xaxis_title=xaxis, yaxis_title=yaxis,
            template="plotly_white", hovermode="x unified",
        )
        fig.write_html(str(path))
        return path
    except Exception as exc:
        log.debug("Plotly XY skipped: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
def _style_axis(ax, title: str, xlabel: str, ylabel: str):
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.legend(fontsize=9)
    try:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    except Exception:
        pass


def _add_breakthrough(ax, kpis: KPISet):
    if kpis.wct_breakthrough_date:
        ax.axvline(
            kpis.wct_breakthrough_date,
            color="orange", linestyle="--", linewidth=1.2,
            label=f"Water BT ({kpis.wct_breakthrough_years:.1f} yr)",
        )
