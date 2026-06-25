"""Standard diagnostic plots for reservoir simulation results.

Each function returns a PlotArtifact.
All plots are generated with matplotlib (always available in the container).
If plotly is installed, an interactive HTML version is also saved alongside.

Canonical plot set (defined by reservoir engineering convention):
  1. FOPR / FWPR / FGPR  — Field production rates vs time
  2. FOPT / FWIT          — Cumulative oil production + water injection vs time
  3. FPR                  — Field average reservoir pressure vs time
  4. WWCT (all wells)     — Well water cut vs time (waterflood diagnostic)
  5. WBHP (all wells)     — Well BHP vs time
  6. Recovery efficiency  — FOPT/FOIP0 vs FWIT/FOIP0 (V_pore injected)
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import warnings

from .models import SummaryFrame, KPISet, PlotArtifact

# suppress matplotlib font warnings in headless docker
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")


def generate_plots(
    sf: SummaryFrame,
    kpis: KPISet,
    output_dir: Path,
) -> list[PlotArtifact]:
    """Generate the full canonical plot set and return PlotArtifact list."""
    if sf.empty or sf.df is None:
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
            # Non-fatal: skip plot if data not available
            pass
    return artifacts


# ─────────────────────────────────────────────────────────────────────────────
# Individual plot functions
# ─────────────────────────────────────────────────────────────────────────────

def _plot_production_rates(
    sf: SummaryFrame, kpis: KPISet, out: Path
) -> Optional[PlotArtifact]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    df = sf.df
    rate_cols = {"FOPR": "Oil Rate (SM³/day)",
                 "FWPR": "Water Prod Rate (SM³/day)",
                 "FGPR": "Gas Rate (SM³/day)",
                 "FWIR": "Water Inj Rate (SM³/day)"}
    present = {k: v for k, v in rate_cols.items() if k in df.columns}
    if not present:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#2563EB", "#16A34A", "#DC2626", "#9333EA"]
    for (col, label), color in zip(present.items(), colors):
        ax.plot(df.index, df[col], label=label, color=color, linewidth=1.8)

    _style_axis(ax, "Field Production & Injection Rates", "Date", "Rate (SM³/day)")
    _add_breakthrough(ax, kpis)
    fig.tight_layout()

    png = out / "01_production_rates.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="production_rates",
        png_path=png,
        html_path=_plotly_rates(df, present, kpis, out, "01_production_rates.html"),
        description="Field oil/water/gas production and water injection rates vs time.",
    )


def _plot_cumulative(
    sf: SummaryFrame, kpis: KPISet, out: Path
) -> Optional[PlotArtifact]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sf.df
    cum_cols = {"FOPT": "Cumulative Oil (SM³)",
                "FWIT": "Cumulative Water Injected (SM³)",
                "FWPT": "Cumulative Water Produced (SM³)"}
    present = {k: v for k, v in cum_cols.items() if k in df.columns}
    if not present:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#2563EB", "#9333EA", "#16A34A"]
    for (col, label), color in zip(present.items(), colors):
        ax.plot(df.index, df[col], label=label, color=color, linewidth=1.8)

    _style_axis(ax, "Cumulative Production & Injection", "Date", "Volume (SM³)")
    fig.tight_layout()

    png = out / "02_cumulative.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="cumulative",
        png_path=png,
        description="Cumulative oil production and water injection vs time.",
    )


def _plot_field_pressure(
    sf: SummaryFrame, kpis: KPISet, out: Path
) -> Optional[PlotArtifact]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sf.df
    if "FPR" not in df.columns:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df.index, df["FPR"], color="#B45309", linewidth=2)
    ax.axhline(kpis.initial_fpr, color="gray", linestyle="--",
               linewidth=1, label=f"Initial: {kpis.initial_fpr:.1f} bar")
    ax.axhline(kpis.final_fpr, color="#DC2626", linestyle="--",
               linewidth=1, label=f"Final: {kpis.final_fpr:.1f} bar")

    _style_axis(ax, "Field Average Reservoir Pressure (FPR)", "Date", "Pressure (bar)")
    fig.tight_layout()

    png = out / "03_field_pressure.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="field_pressure",
        png_path=png,
        description="Field average reservoir pressure vs time.",
    )


def _plot_water_cut(
    sf: SummaryFrame, kpis: KPISet, out: Path
) -> Optional[PlotArtifact]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sf.df
    wwct_cols = [c for c in df.columns if c.startswith("WWCT")]
    has_field_rates = "FWPR" in df.columns and "FOPR" in df.columns
    if not wwct_cols and not has_field_rates:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))

    if wwct_cols:
        for col in wwct_cols:
            well = col.split(":", 1)[-1] if ":" in col else col
            ax.plot(df.index, df[col], linewidth=1.6, label=well)
    elif has_field_rates:
        total = df["FWPR"] + df["FOPR"]
        fwct = df["FWPR"] / total.where(total > 0)
        ax.plot(df.index, fwct, color="#16A34A", linewidth=2, label="Field WCT")

    ax.axhline(0.05, color="orange", linestyle=":", linewidth=1, label="BT threshold 5%")
    ax.set_ylim(0, 1.05)
    _add_breakthrough(ax, kpis)
    _style_axis(ax, "Well / Field Water Cut (WWCT)", "Date", "Water Cut (fraction)")
    fig.tight_layout()

    png = out / "04_water_cut.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="water_cut",
        png_path=png,
        description="Well water cut vs time — key waterflood performance indicator.",
    )


def _plot_bhp(
    sf: SummaryFrame, kpis: KPISet, out: Path
) -> Optional[PlotArtifact]:
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
        ax.plot(df.index, df[col], linewidth=1.6, label=well)

    _style_axis(ax, "Well Bottom-Hole Pressure (WBHP)", "Date", "BHP (bar)")
    fig.tight_layout()

    png = out / "05_bhp.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="bhp",
        png_path=png,
        description="Well bottom-hole pressures vs time.",
    )


def _plot_recovery_efficiency(
    sf: SummaryFrame, kpis: KPISet, out: Path
) -> Optional[PlotArtifact]:
    """Recovery efficiency (FOPT/FOIP0) vs. pore-volumes injected (FWIT/FOIP0).
    This is the first plot a waterflood reservoir engineer checks.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = sf.df
    if kpis.foip_initial is None or kpis.foip_initial == 0:
        return None
    if "FOPT" not in df.columns or "FWIT" not in df.columns:
        return None

    re = df["FOPT"] / kpis.foip_initial
    pvi = df["FWIT"] / kpis.foip_initial   # pore volumes injected (approx)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(pvi, re, color="#2563EB", linewidth=2)
    ax.set_xlabel("Pore Volumes Injected (FWIT / FOIP₀)")
    ax.set_ylabel("Recovery Factor (FOPT / FOIP₀)")
    ax.set_title("Recovery Efficiency Curve")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    png = out / "06_recovery_efficiency.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return PlotArtifact(
        name="recovery_efficiency",
        png_path=png,
        description="Recovery factor vs pore volumes injected — primary waterflood efficiency diagnostic.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Plotly helpers (optional, non-fatal if plotly not installed)
# ─────────────────────────────────────────────────────────────────────────────

def _plotly_rates(df, present: dict, kpis: KPISet, out: Path, filename: str) -> Optional[Path]:
    try:
        import plotly.graph_objects as go
        fig = go.Figure()
        colors = ["#2563EB", "#16A34A", "#DC2626", "#9333EA"]
        for (col, label), color in zip(present.items(), colors):
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col],
                mode="lines", name=label,
                line=dict(color=color, width=2),
            ))
        if kpis.wct_breakthrough_date:
            fig.add_vline(
                x=kpis.wct_breakthrough_date,
                line_dash="dash", line_color="orange",
                annotation_text="Water BT",
            )
        fig.update_layout(
            title="Field Production & Injection Rates",
            xaxis_title="Date",
            yaxis_title="Rate (SM³/day)",
            template="plotly_white",
            hovermode="x unified",
        )
        html_path = out / filename
        fig.write_html(str(html_path))
        return html_path
    except ImportError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Shared styling
# ─────────────────────────────────────────────────────────────────────────────

def _style_axis(ax, title: str, xlabel: str, ylabel: str):
    import matplotlib.dates as mdates
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.legend(fontsize=9)
    try:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        import matplotlib.pyplot as plt
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
