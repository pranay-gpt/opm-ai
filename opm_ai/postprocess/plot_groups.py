"""Plotly builders for the priority vector families.

One builder per group; mirrors the categorizer families exactly. Each
function only emits a trace for columns that actually exist in the
DataFrame (spec: "plot only what is present"). No zero-fills, no
fabrication.

Reuses the sanitization and hovertemplate style from opm_ai/postprocess/plots.py
so the existing Plotly conventions carry over.

Task 11 additions:
- per_property mode: when True, group traces by vector (e.g., WOPR) across all wells
  instead of by well. Returns one figure per vector.
- unit_system: 'FIELD' or 'METRIC' - changes axis labels only (no value conversion)
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from opm_ai.postprocess.plots import _sanitize_water_rate


_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

_WATER_KEYWORDS = ("WWPR", "WWPT", "WWIR", "WWIT", "WWCT", "FWPR", "FWPT")

# Unit system label mapping (Task 11: axis relabeling only, no value conversion)
_UNIT_LABELS = {
    "FIELD": {
        "rate_oil": "STB/day",
        "rate_water": "STB/day",
        "rate_gas": "MSCF/day",
        "cum_oil": "STB",
        "cum_water": "STB",
        "cum_gas": "MSCF",
        "pressure": "psia",
        "volume_rate": "Rate",
        "volume_cum": "Cumulative Volume",
    },
    "METRIC": {
        "rate_oil": "m³/day",
        "rate_water": "m³/day",
        "rate_gas": "SM³/day",
        "cum_oil": "m³",
        "cum_water": "m³",
        "cum_gas": "SM³",
        "pressure": "bar",
        "volume_rate": "Rate",
        "volume_cum": "Cumulative Volume",
    },
}

# Human-readable labels for vector short codes.
# Used in plot titles and axis labels instead of short codes like "FOPR"/"WOPR".
_VECTOR_LABELS = {
    # Field rates
    "FOPR": "Oil Rate",
    "FWPR": "Water Rate",
    "FGPR": "Gas Rate",
    # Field cumulative
    "FOPT": "Oil Cumulative",
    "FWPT": "Water Cumulative",
    "FGPT": "Gas Cumulative",
    # Field derived
    "FWCT": "Water Cut",
    "FGOR": "GOR",
    "FPR": "Avg Pressure",
    # Well rates
    "WOPR": "Oil Rate",
    "WWPR": "Water Rate",
    "WGPR": "Gas Rate",
    "WBHP": "BHP",
    "WGOR": "GOR",
    "WWCT": "Water Cut",
    # Well cumulative
    "WOPT": "Oil Cumulative",
    "WWPT": "Water Cumulative",
    "WGPT": "Gas Cumulative",
    # Well injection
    "WGIR": "Gas Injection Rate",
    "WWIR": "Water Injection Rate",
    "WOIR": "Oil Injection Rate",
    "WGIT": "Gas Injection Cumulative",
    "WWIT": "Water Injection Cumulative",
    # Missing injection cumulative (oil)
    "WOIT": "Oil Injection Cumulative",
}

# Map each keyword to its unit label category
_VECTOR_UNIT_CATEGORY = {
    # Field rates
    "FOPR": "rate_oil",
    "FWPR": "rate_water",
    "FGPR": "rate_gas",
    # Field cumulative
    "FOPT": "cum_oil",
    "FWPT": "cum_water",
    "FGPT": "cum_gas",
    # Field derived
    "FWCT": None,  # Special: %
    "FGOR": None,  # Special: gas/oil
    "FPR": "pressure",
    # Well rates
    "WOPR": "rate_oil",
    "WWPR": "rate_water",
    "WGPR": "rate_gas",
    "WBHP": "pressure",
    "WGOR": None,  # Special: gas/oil
    "WWCT": None,  # Special: %
    # Well cumulative
    "WOPT": "cum_oil",
    "WWPT": "cum_water",
    "WGPT": "cum_gas",
    # Well injection
    "WGIR": "rate_gas",
    "WWIR": "rate_water",
    "WOIR": "rate_oil",
    "WGIT": "cum_gas",
    "WWIT": "cum_water",
    "WOIT": "cum_oil",
}


def _get_y_label(kw: str, labels: dict) -> str:
    """Generate y-axis label for a keyword using unit system labels."""
    category = _VECTOR_UNIT_CATEGORY.get(kw)
    vec_label = _VECTOR_LABELS.get(kw, kw)

    if category is None:
        # Special cases: %, GOR, etc.
        if kw in ("FWCT", "WWCT"):
            return "Water Cut (%)"
        if kw in ("FGOR", "WGOR"):
            return f"GOR ({labels['rate_gas']}/{labels['rate_oil']})"
        return vec_label

    if category.startswith("rate_"):
        return f"{vec_label} ({labels[category]})"
    if category.startswith("cum_"):
        return f"{vec_label} ({labels[category]})"
    if category == "pressure":
        return f"{vec_label} ({labels['pressure']})"
    return vec_label


def _get_unit_labels(unit_system: str) -> dict:
    """Get label mapping for unit system. Defaults to FIELD."""
    return _UNIT_LABELS.get(unit_system.upper(), _UNIT_LABELS["FIELD"])


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


# ── Per-property mode helpers ──────────────────────────────────────────────

def _well_figure_per_property(
    df: pd.DataFrame,
    wells: list[str],
    keywords: tuple[str, ...],
    group: str,
    *,
    log_scale: bool = False,
    vector_filter: list[str] | None = None,
    unit_system: str = "FIELD",
) -> list[go.Figure]:
    """Per-property mode: one figure per vector keyword, all wells on each figure."""
    labels = _get_unit_labels(unit_system)

    # Determine which keywords actually have data
    active_keywords = []
    for kw in keywords:
        if vector_filter and kw not in vector_filter:
            continue
        # Check if any well has this keyword
        has_data = any(f"{kw}:{well}" in df.columns for well in wells)
        if has_data:
            active_keywords.append(kw)

    figures = []
    for kw in active_keywords:
        fig = go.Figure()
        if df.empty or "TIME" not in df.columns:
            figures.append(_apply_log(fig, log_scale))
            continue

        # Use shared helper for y-axis label
        y_label = _get_y_label(kw, labels)
        vec_label = _VECTOR_LABELS.get(kw, kw)

        for well in wells:
            col = f"{kw}:{well}"
            if col not in df.columns:
                continue
            y = df[col]
            if kw in ("WWPR", "WWPT", "WWIR", "WWIT", "WWCT"):
                y = _sanitize_water_rate(y)
            fig.add_trace(go.Scatter(
                x=_time(df), y=y, mode="lines",
                name=f"{vec_label} {well}",
                line=dict(color=_COLORS[wells.index(well) % len(_COLORS)]),
                hovertemplate=f"{vec_label} {well}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
            ))
        title = f"{group.replace('_', ' ').title()} - {vec_label}"
        fig.update_layout(**_base_layout(title, y_label))
        figures.append(_apply_log(fig, log_scale))
    return figures


def _field_figure_per_property(
    df: pd.DataFrame,
    wells: list[str],
    keywords: tuple[str, ...],
    group: str,
    *,
    log_scale: bool = False,
    vector_filter: list[str] | None = None,
    unit_system: str = "FIELD",
) -> list[go.Figure]:
    """Per-property mode for field groups: one figure per vector keyword."""
    labels = _get_unit_labels(unit_system)

    # Determine which keywords actually have data
    active_keywords = []
    for kw in keywords:
        if vector_filter and kw not in vector_filter:
            continue
        if kw in df.columns:
            active_keywords.append(kw)

    figures = []
    for kw in active_keywords:
        fig = go.Figure()
        if df.empty or "TIME" not in df.columns:
            figures.append(_apply_log(fig, log_scale))
            continue

        # Use shared helper for y-axis label
        y_label = _get_y_label(kw, labels)
        vec_label = _VECTOR_LABELS.get(kw, kw)

        y = df[kw]
        if kw in ("FWPR", "FWPT", "FWCT"):
            y = _sanitize_water_rate(y)
        fig.add_trace(go.Scatter(
            x=_time(df), y=y, mode="lines",
            name=vec_label,
            line=dict(color=_COLORS[0]),
            hovertemplate=f"{vec_label}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
        ))
        title = f"{group.replace('_', ' ').title()} - {vec_label}"
        fig.update_layout(**_base_layout(title, y_label))
        figures.append(_apply_log(fig, log_scale))
    return figures


# ── Well figure builder (shared) ──────────────────────────────────────────

def _well_figure(
    df: pd.DataFrame,
    wells: list[str],
    keywords: tuple[str, ...],
    title: str,
    y_title: str,
    *,
    log_scale: bool = False,
    vector_filter: list[str] | None = None,
    unit_system: str = "FIELD",
) -> go.Figure:
    """Build a well figure with one trace per well per keyword."""
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
            y = df[col]
            if kw in ("WWPR", "WWPT", "WWIR", "WWIT", "WWCT"):
                y = _sanitize_water_rate(y)
            is_rate = kw in ("WOPR", "WWPR", "WGPR", "WGIR", "WWIR", "WOIR")
            is_bhp = kw == "WBHP"
            dash = "dot" if is_rate and not is_bhp else "solid"
            # Use human-readable label for trace name
            vec_label = _VECTOR_LABELS.get(kw, kw)
            fig.add_trace(go.Scatter(
                x=_time(df), y=y, mode="lines",
                name=f"{vec_label} {well}",
                line=dict(color=color, dash=dash),
                hovertemplate=f"{vec_label} {well}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
            ))
    fig.update_layout(**_base_layout(title, y_title))
    return _apply_log(fig, log_scale)


# ── Field plot builders ──────────────────────────────────────────────────

def plot_field_rates(
    df: pd.DataFrame,
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
    unit_system: str = "FIELD",
) -> go.Figure:
    """Plot field-level production rates (FOPR, FWPR, FGPR)."""
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    requested = vectors or ["FOPR", "FWPR", "FGPR"]
    labels_map = _get_unit_labels(unit_system)
    colors = {"FOPR": "#1f77b4", "FWPR": "#ff7f0e", "FGPR": "#2ca02c"}
    for i, col in enumerate(requested):
        if col not in df.columns:
            continue
        label = _get_y_label(col, labels_map)
        fig.add_trace(go.Scatter(
            x=_time(df), y=df[col], mode="lines",
            name=label,
            line=dict(color=colors.get(col, _COLORS[i % len(_COLORS)])),
            hovertemplate=f"{label}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
        ))
    fig.update_layout(**_base_layout("Production Rates", labels_map["volume_rate"]))
    return _apply_log(fig, log_scale)


def plot_field_cumulative(
    df: pd.DataFrame,
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
    unit_system: str = "FIELD",
) -> go.Figure:
    """Plot field-level cumulative production (FOPT, FWPT, FGPT)."""
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    requested = vectors or ["FOPT", "FWPT", "FGPT"]
    labels_map = _get_unit_labels(unit_system)
    colors = {"FOPT": "#1f77b4", "FWPT": "#ff7f0e", "FGPT": "#2ca02c"}
    for i, col in enumerate(requested):
        if col not in df.columns:
            continue
        label = _get_y_label(col, labels_map)
        fig.add_trace(go.Scatter(
            x=_time(df), y=df[col], mode="lines",
            name=label,
            line=dict(color=colors.get(col, _COLORS[i % len(_COLORS)])),
            hovertemplate=f"{label}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
        ))
    fig.update_layout(**_base_layout("Cumulative Production", labels_map["volume_cum"]))
    return _apply_log(fig, log_scale)


def plot_field_derived(
    df: pd.DataFrame,
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
    unit_system: str = "FIELD",
) -> go.Figure:
    """Plot field-level derived variables (FWCT, FGOR, FPR).

    FWCT is computed from FOPR+FWPR when the FWCT column is missing.
    """
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    requested = vectors or ["FWCT", "FGOR", "FPR"]
    labels_map = _get_unit_labels(unit_system)

    # Field Water Cut - use column if present, otherwise compute from rates
    if "FWCT" in requested:
        if "FWCT" in df.columns:
            label = "Water Cut (%)"
            y = df["FWCT"] * 100
        elif "FOPR" in df.columns and "FWPR" in df.columns:
            fwpr = _sanitize_water_rate(df["FWPR"])
            liq = df["FOPR"] + fwpr
            wc_pct = (fwpr / liq.replace(0, np.nan)) * 100
            label = "Water Cut (%)"
            y = wc_pct
        else:
            # Cannot compute, skip
            pass
        if "FWCT" in requested and (("FWCT" in df.columns) or ("FOPR" in df.columns and "FWPR" in df.columns)):
            fig.add_trace(go.Scatter(
                x=_time(df), y=y, mode="lines",
                name=label,
                line=dict(color=_COLORS[0]),
                hovertemplate=f"{label}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
            ))

    for col in requested:
        if col == "FWCT":
            continue  # Already handled above
        if col not in df.columns:
            continue
        label = _get_y_label(col, labels_map)
        fig.add_trace(go.Scatter(
            x=_time(df), y=df[col], mode="lines",
            name=label,
            line=dict(color=_COLORS[1 if col == "FGOR" else 2]),
            hovertemplate=f"{label}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
        ))
    # Derived quantities don't share a single unit; use generic
    fig.update_layout(**_base_layout("Derived Variables", "Value"))
    return _apply_log(fig, log_scale)


# ── Well plot builders ──────────────────────────────────────────────────

def plot_well_rates(
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
    unit_system: str = "FIELD",
) -> go.Figure:
    """Plot well-level rates (WOPR, WWPR, WGPR, WBHP, WGOR, WWCT)."""
    # In regular mode, we can't show multiple units on one y-axis.
    # Use the first selected vector's unit as representative, or default to oil rate.
    labels_map = _get_unit_labels(unit_system)
    if vectors:
        # Find first vector's category
        for v in vectors:
            cat = _VECTOR_UNIT_CATEGORY.get(v)
            if cat and cat.startswith("rate_"):
                y_label = f"Rate ({labels_map[cat]})"
                break
            elif cat == "pressure":
                y_label = f"BHP ({labels_map['pressure']})"
                break
        else:
            y_label = f"Rate ({labels_map['rate_oil']})"
    else:
        y_label = f"Rate ({labels_map['rate_oil']})"
    return _well_figure(
        df, wells, ("WOPR", "WWPR", "WGPR", "WBHP", "WGOR", "WWCT"),
        "Well Rates", y_label,
        log_scale=log_scale, vector_filter=vectors, unit_system=unit_system,
    )


def plot_well_cumulative(
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
    unit_system: str = "FIELD",
) -> go.Figure:
    """Plot well-level cumulative production (WOPT, WWPT, WGPT)."""
    labels_map = _get_unit_labels(unit_system)
    if vectors:
        for v in vectors:
            cat = _VECTOR_UNIT_CATEGORY.get(v)
            if cat and cat.startswith("cum_"):
                y_label = f"Cumulative Volume ({labels_map[cat]})"
                break
        else:
            y_label = f"Cumulative Volume ({labels_map['cum_oil']})"
    else:
        y_label = f"Cumulative Volume ({labels_map['cum_oil']})"
    return _well_figure(
        df, wells, ("WOPT", "WWPT", "WGPT"),
        "Well Cumulative", y_label,
        log_scale=log_scale, vector_filter=vectors, unit_system=unit_system,
    )


def plot_well_injection(
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
    unit_system: str = "FIELD",
) -> go.Figure:
    """Plot well-level injection (WGIR, WWIR, WOIR, WGIT, WWIT)."""
    labels_map = _get_unit_labels(unit_system)
    if vectors:
        # Use the first selected vector's category for the generic y-axis label
        for v in vectors:
            cat = _VECTOR_UNIT_CATEGORY.get(v)
            if cat and cat.startswith("rate_"):
                y_label = f"Injection Rate ({labels_map[cat]})"
                break
            elif cat and cat.startswith("cum_"):
                y_label = f"Injection Cumulative ({labels_map[cat]})"
                break
        else:
            y_label = f"Injection Rate ({labels_map['rate_gas']})"
    else:
        y_label = f"Injection Rate ({labels_map['rate_gas']})"
    return _well_figure(
        df, wells, ("WGIR", "WWIR", "WOIR", "WGIT", "WWIT"),
        "Well Injection", y_label,
        log_scale=log_scale, vector_filter=vectors, unit_system=unit_system,
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

_DISPATCH_PER_PROPERTY: dict[str, Callable[..., list[go.Figure]]] = {
    "field_rates": _field_figure_per_property,
    "field_cumulative": _field_figure_per_property,
    "field_derived": _field_figure_per_property,
    "well_rates": _well_figure_per_property,
    "well_cumulative": _well_figure_per_property,
    "well_injection": _well_figure_per_property,
}

_WELL_KEYWORDS = {
    "well_rates": ("WOPR", "WWPR", "WGPR", "WBHP", "WGOR", "WWCT"),
    "well_cumulative": ("WOPT", "WWPT", "WGPT"),
    "well_injection": ("WGIR", "WWIR", "WOIR", "WGIT", "WWIT"),
}


def plot_group(
    group: str,
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None,
    *,
    log_scale: bool = False,
    per_property: bool = False,
    unit_system: str = "FIELD",
) -> go.Figure | list[go.Figure]:
    """Dispatch to the appropriate plot builder for a vector group."""
    if per_property:
        dispatcher = _DISPATCH_PER_PROPERTY
        keywords = _WELL_KEYWORDS.get(group, ())
    else:
        dispatcher = _DISPATCH
        keywords = ()
    builder = dispatcher.get(group)
    if not builder:
        # Return empty figure instead of raising
        fig = go.Figure()
        fig.update_layout(title=f"Unknown group: {group}")
        return _apply_log(fig, log_scale)
    if per_property:
        return builder(df, wells, keywords, group, log_scale=log_scale, vector_filter=vectors, unit_system=unit_system)
    if group.startswith("field_"):
        return builder(df, vectors=vectors, log_scale=log_scale, unit_system=unit_system)
    return builder(df, wells=wells, vectors=vectors, log_scale=log_scale, unit_system=unit_system)