"""Data contracts for Part 5 — Post-Processing.

These dataclasses are the currency passed between
kpi_extractor → plot_engine → resinsight_bridge → chat/explainer.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
import datetime


@dataclass
class SummaryFrame:
    """Thin wrapper around the pandas DataFrame loaded from SMSPEC/UNSMRY.

    ``df`` columns are SUMMARY vector mnemonics (FOPR, FWCT, WBHP:PROD1, …).
    ``dates`` is the time axis as datetime objects.
    """
    df: Any = None          # pandas.DataFrame | None
    dates: list = field(default_factory=list)
    vectors: list[str] = field(default_factory=list)
    case_name: str = ""

    @classmethod
    def empty(cls) -> "SummaryFrame":
        return cls(df=None, dates=[], vectors=[], case_name="")

    @property
    def empty(self) -> bool:           # type: ignore[override]
        return self.df is None or (hasattr(self.df, "empty") and self.df.empty)


@dataclass
class KPISet:
    """Reservoir engineering KPIs computed from the summary vectors.

    All rates are in surface units as reported by OPM Flow.
    Pressures in bar. Volumes in SM3 (or MSCM for gas).
    """
    # ── Cumulative production / injection ──────────────────────────────────
    fopt: Optional[float] = None   # Field Oil Production Total  [SM3]
    fwpt: Optional[float] = None   # Field Water Production Total [SM3]
    fgpt: Optional[float] = None   # Field Gas Production Total   [SM3]
    fwit: Optional[float] = None   # Field Water Injection Total  [SM3]
    fgit: Optional[float] = None   # Field Gas Injection Total    [SM3]

    # ── Peak rates ─────────────────────────────────────────────────────────
    peak_fopr: Optional[float] = None   # peak Field Oil Production Rate  [SM3/day]
    peak_fopr_date: Optional[datetime.datetime] = None
    peak_fwir: Optional[float] = None   # peak Field Water Injection Rate [SM3/day]

    # ── Pressure ───────────────────────────────────────────────────────────
    initial_fpr: Optional[float] = None   # Field Avg Pressure at t=0  [bar]
    final_fpr: Optional[float] = None     # Field Avg Pressure at t=end [bar]
    pressure_drop: Optional[float] = None # initial − final             [bar]

    # ── Water breakthrough ─────────────────────────────────────────────────
    # Breakthrough defined as first timestep where any producer WWCT > 0.05
    wct_breakthrough_date: Optional[datetime.datetime] = None
    wct_breakthrough_years: Optional[float] = None  # years from t=0
    final_field_wct: Optional[float] = None         # FWPR/(FWPR+FOPR) at end

    # ── Recovery ───────────────────────────────────────────────────────────
    foip_initial: Optional[float] = None   # FOIP at t=0  [SM3]  (proxy for STOIIP)
    recovery_factor: Optional[float] = None  # FOPT / FOIP_initial  [fraction]

    # ── Simulation performance ─────────────────────────────────────────────
    total_timesteps: Optional[int] = None
    avg_newton_iters: Optional[float] = None
    total_cpu_seconds: Optional[float] = None

    # ── Available vectors (for UI display) ────────────────────────────────
    available_vectors: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "KPISet":
        return cls()

    def as_dict(self) -> dict:
        """Return only non-None KPIs as a plain dict — safe to serialise to JSON."""
        import dataclasses
        return {k: v for k, v in dataclasses.asdict(self).items()
                if v is not None and k != "available_vectors"}

    def narrative_bullets(self) -> list[str]:
        """Return human-readable bullet strings for each non-None KPI.
        Used by Part 7 (explainer) as structured input.
        """
        bullets = []
        if self.fopt is not None:
            bullets.append(f"Cumulative oil production (FOPT): {self.fopt:,.0f} SM³")
        if self.fwit is not None:
            bullets.append(f"Cumulative water injection (FWIT): {self.fwit:,.0f} SM³")
        if self.recovery_factor is not None:
            bullets.append(f"Recovery factor: {self.recovery_factor*100:.1f}% of initial STOIIP")
        if self.wct_breakthrough_years is not None:
            bullets.append(f"Water breakthrough at year {self.wct_breakthrough_years:.2f}")
        if self.final_field_wct is not None:
            bullets.append(f"Final field water cut: {self.final_field_wct*100:.1f}%")
        if self.pressure_drop is not None:
            bullets.append(f"Reservoir pressure drop: {self.pressure_drop:.1f} bar "
                           f"({self.initial_fpr:.1f} → {self.final_fpr:.1f} bar)")
        if self.peak_fopr is not None:
            bullets.append(f"Peak oil rate (FOPR): {self.peak_fopr:.1f} SM³/day")
        return bullets


@dataclass
class PlotArtifact:
    """A single generated plot file."""
    name: str            # e.g. "FOPR_vs_time"
    png_path: Path
    html_path: Optional[Path] = None   # Plotly interactive version
    description: str = ""


@dataclass
class PostProcessResult:
    """Full output of the post-processing pipeline.

    This object is the hand-off to Part 6 (chat) and Part 7 (explainer).
    """
    simulation_result: Any          # SimulationResult from opm_ai.runner
    kpis: KPISet
    summary_frame: SummaryFrame
    plots: list[PlotArtifact] = field(default_factory=list)
    resinsight_launched: bool = False
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None

    def plot_paths(self) -> list[Path]:
        return [p.png_path for p in self.plots]
