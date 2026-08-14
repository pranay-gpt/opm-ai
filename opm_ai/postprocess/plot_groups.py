"""Plotly builders for the priority vector families.

One builder per group; mirrors the categorizer families exactly. Each
function only emits a trace for columns that actually exist in the
DataFrame (spec: "plot only what is present"). No zero-fills, no
fabrication.

Reuses the sanitization and hovertemplate style from opm_ai/postprocess/plots.py
so the existing Plotly conventions carry over.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from opm_ai.postprocess.plots import _sanitize_water_rate


_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

_WATER_KEYWORDS = ("WWPR", "WWPT", "WWIR", "WWIT", "WWCT", "FWPR", "FWPT")


def _time(df: pd.DataFrame) -> pd.Series:
    return df["TIME"] if "TIME" in df.columns else pd.Series(dtype=float)


def _apply_log(fig: go.Figure, log_scale: bool) -> go.Figure:
    if log_scale:
        fig.update_layout(yaxis_type="log")
    return fig


def _base_layout(title: str, y_title: str, height: int = 500) -> dict:
    return dict(
        title=title,
        xaxis_title="Time (days)",
        yaxis_title=y_title,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        height=height,
    )


# ── Field groups ────────────────────────────────────────────────────────


def plot_field_rates(
    df: pd.DataFrame,
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    """Plot field-level production rates (FOPR, FWPR, FGPR)."""
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    requested = vectors or ["FOPR", "FWPR", "FGPR"]
    labels = {
        "FOPR": "Field Oil Rate (STB/day)",
        "FWPR": "Field Water Rate (STB/day)",
        "FGPR": "Field Gas Rate (MSCF/day)",
    }
    colors = {"FOPR": "#1f77b4", "FWPR": "#ff7f0e", "FGPR": "#2ca02c"}
    for i, col in enumerate(requested):
        if col not in df.columns:
            continue
        label = labels.get(col, col)
        name = f"{col} - {label}"
        fig.add_trace(go.Scatter(
            x=_time(df), y=df[col], mode="lines",
            name=name,
            line=dict(color=colors.get(col, _COLORS[i % len(_COLORS)])),
            hovertemplate=f"{label}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
        ))
    fig.update_layout(**_base_layout("Production Rates", "Rate"))
    return _apply_log(fig, log_scale)


def plot_field_cumulative(
    df: pd.DataFrame,
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    """Plot field-level cumulative production (FOPT, FWPT, FGPT)."""
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    requested = vectors or ["FOPT", "FWPT", "FGPT"]
    labels = {
        "FOPT": "Cumulative Oil (STB)",
        "FWPT": "Cumulative Water (STB)",
        "FGPT": "Cumulative Gas (MSCF)",
    }
    colors = {"FOPT": "#1f77b4", "FWPT": "#ff7f0e", "FGPT": "#2ca02c"}
    for i, col in enumerate(requested):
        if col not in df.columns:
            continue
        label = labels.get(col, col)
        name = f"{col} - {label}"
        fig.add_trace(go.Scatter(
            x=_time(df), y=df[col], mode="lines",
            name=name,
            line=dict(color=colors.get(col, _COLORS[i % len(_COLORS)])),
            hovertemplate=f"{label}: %{{y:.0f}}<br>Time: %{{x:.1f}} days<extra></extra>",
        ))
    fig.update_layout(**_base_layout("Cumulative Production", "Cumulative Volume"))
    return _apply_log(fig, log_scale)


def plot_field_derived(
    df: pd.DataFrame,
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    """Plot field-level derived quantities (FWCT, FGOR, FPR).

    FWCT is computed from FOPR+FWPR when the FWCT column is missing.
    """
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    requested = vectors or ["FWCT", "FGOR", "FPR"]

    # Field Water Cut - use column if present, otherwise compute from rates
    if "FWCT" in requested:
        if "FWCT" in df.columns:
            fig.add_trace(go.Scatter(
                x=_time(df), y=df["FWCT"], mode="lines",
                name="FWCT - Field Water Cut (%)",
                line=dict(color="#ff7f0e", width=2),
                hovertemplate="Water Cut: %{y:.1f}%<br>Time: %{x:.1f} days<extra></extra>",
            ))
        elif "FOPR" in df.columns and "FWPR" in df.columns:
            fwpr = _sanitize_water_rate(df["FWPR"])
            liq = df["FOPR"] + fwpr
            wc_pct = (fwpr / liq.replace(0, np.nan)) * 100
            fig.add_trace(go.Scatter(
                x=_time(df), y=wc_pct, mode="lines",
                name="FWCT - Field Water Cut (%)",
                line=dict(color="#ff7f0e", width=2),
                hovertemplate="Water Cut: %{y:.1f}%<br>Time: %{x:.1f} days<extra></extra>",
            ))

    # Field GOR
    if "FGOR" in requested and "FGOR" in df.columns:
        fig.add_trace(go.Scatter(
            x=_time(df), y=df["FGOR"], mode="lines",
            name="Field GOR (MSCF/STB)",
            line=dict(color="#2ca02c"),
            hovertemplate="Field GOR: %{y:.1f} MSCF/STB<br>Time: %{x:.1f} days<extra></extra>",
        ))

    # Field Average Pressure
    if "FPR" in requested and "FPR" in df.columns:
        fig.add_trace(go.Scatter(
            x=_time(df), y=df["FPR"], mode="lines",
            name="Field Avg Pressure (psia)",
            line=dict(color="#d62728"),
            hovertemplate="Field Avg Pressure: %{y:.1f} psia<br>Time: %{x:.1f} days<extra></extra>",
        ))

    fig.update_layout(**_base_layout("Field Derived", "Value"))
    return _apply_log(fig, log_scale)


# ── Well groups ─────────────────────────────────────────────────────────


def _well_figure(
    df: pd.DataFrame,
    wells: list[str],
    keywords: tuple[str, ...],
    title: str,
    y_title: str,
    *,
    log_scale: bool = False,
    vector_filter: list[str] | None = None,
) -> go.Figure:
    """Shared well plotting logic: one trace per well per vector keyword.

    Rates use dashed lines; BHP uses solid lines.
    """
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)

    for i, well in enumerate(wells):
        color = _COLORS[i % len(_COLORS)]
        for kw in keywords:
            if vector_filter and kw not in vector_filter:
                continue
            col = f"{kw}:{well}"
            if col not in df.columns:
                continue
            # Sanitize water rates (WWPR, WWPT, WWIR, WWIT, WWCT, FWPR, FWPT)
            y = _sanitize_water_rate(df[col]) if kw in _WATER_KEYWORDS else df[col]
            # Dashed for rates, solid for BHP and cumulative
            is_rate = kw in ("WOPR", "WWPR", "WGPR", "WGIR", "WWIR", "WOIR")
            is_bhp = kw == "WBHP"
            dash = "dot" if is_rate and not is_bhp else "solid"
            fig.add_trace(go.Scatter(
                x=_time(df), y=y, mode="lines",
                name=f"{kw} {well}",
                line=dict(color=color, dash=dash),
                hovertemplate=f"{kw} {well}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
            ))
    fig.update_layout(**_base_layout(title, y_title))
    return _apply_log(fig, log_scale)


def plot_well_rates(
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    """Plot well-level rates (WOPR, WWPR, WGPR, WBHP, WGOR, WWCT)."""
    return _well_figure(
        df, wells, ("WOPR", "WWPR", "WGPR", "WBHP", "WGOR", "WWCT"),
        "Well Rates", "Rate",
        log_scale=log_scale, vector_filter=vectors,
    )


def plot_well_cumulative(
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    """Plot well-level cumulative production (WOPT, WWPT, WGPT)."""
    return _well_figure(
        df, wells, ("WOPT", "WWPT", "WGPT"),
        "Well Cumulative", "Cumulative Volume",
        log_scale=log_scale, vector_filter=vectors,
    )


def plot_well_injection(
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    """Plot well-level injection (WGIR, WWIR, WOIR, WGIT, WWIT)."""
    return _well_figure(
        df, wells, ("WGIR", "WWIR", "WOIR", "WGIT", "WWIT"),
        "Well Injection", "Rate / Cumulative",
        log_scale=log_scale, vector_filter=vectors,
    )


# ── Dispatcher ──────────────────────────────────────────────────────────


_DISPATCH: dict[str, Callable[..., go.Figure]] = {
    "field_rates": plot_field_rates,
    "field_cumulative": plot_field_cumulative,
    "field_derived": plot_field_derived,
    "well_rates": plot_well_rates,
    "well_cumulative": plot_well_cumulative,
    "well_injection": plot_well_injection,
}


def plot_group(
    group: str,
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    """Dispatch to the right plot_* function. Raises ValueError on unknown group."""
    fn = _DISPATCH.get(group)
    if fn is None:
        raise ValueError(f"Unknown group: {group!r}. Known: {sorted(_DISPATCH)}")
    if group.startswith("field_"):
        return fn(df, vectors=vectors, log_scale=log_scale)
    return fn(df, wells, vectors=vectors, log_scale=log_scale)
