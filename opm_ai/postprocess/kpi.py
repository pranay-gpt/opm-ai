"""KPI extraction from simulation results."""

from typing import Any

import math
import numpy as np
import pandas as pd


def _sanitize_float(val: float) -> float:
    """Normalize negative zero to positive zero, return NaN/Inf as-is for sanitization."""
    if val == 0.0:
        return 0.0  # -0.0 becomes 0.0
    return val


def extract_kpis(df: pd.DataFrame) -> dict[str, Any]:
    """
    Extract Key Performance Indicators from summary DataFrame.

    Args:
        df: DataFrame from read_summary() with TIME column and well vectors.

    Returns:
        Dictionary of KPIs including:
        - days: total simulation days (> 0)
        - field_oil_recovery: cumulative oil produced (STB)
        - field_water_recovery: cumulative water produced (STB)
        - field_gas_recovery: cumulative gas produced (MSCF)
        - fopt_recovery: alias for field_oil_recovery (FOPT-based)
        - fwpt_recovery: alias for field_water_recovery (FWPT-based)
        - fgpt_recovery: alias for field_gas_recovery (FGPT-based)
        - max_watercut: maximum water cut observed (fraction 0-1)
        - water_breakthrough_day: day when watercut first exceeds 1%
        - plateau_duration_days: days with oil rate above 90% of initial
        - avg_gor: average GOR over simulation
        - sweep_efficiency: estimated sweep efficiency (0.0 if unknown)
        - producer_count: number of producing wells
        - For each producer: *_cum_oil, *_cum_water, *_cum_gas, *_final_bhp,
          *_max_watercut, *_final_watercut, *_avg_gor, *_final_gor, *_initial_oil_rate,
          *_final_oil_rate, *_avg_oil_rate, *_avg_bhp
    """
    if df.empty or 'TIME' not in df.columns:
        return {"days": 0.0}

    kpis = {}

    # Total simulation days
    kpis["days"] = float(df['TIME'].max())
    kpis["timesteps"] = len(df)

    # Find field totals and well vectors
    field_cols = [c for c in df.columns if c.startswith(('FOPR', 'FWPR', 'FGPR', 'FOPT', 'FWPT', 'FGPT', 'FGOR'))]
    well_cols = [c for c in df.columns if ':' in c and not c.startswith(('FOPR', 'FWPR', 'FGPR', 'FOPT', 'FWPT', 'FGPT'))]

    # Field oil rate and cumulative
    fopr_col = _find_col(df, 'FOPR')
    foip_col = _find_col(df, 'FOPT')
    fwpr_col = _find_col(df, 'FWPR')
    fwpt_col = _find_col(df, 'FWPT')
    fgpr_col = _find_col(df, 'FGPR')
    fgpt_col = _find_col(df, 'FGPT')
    fg_or_col = _find_col(df, 'FGOR')

    if fopr_col and len(df) > 0:
        kpis["field_initial_oil_rate"] = float(df[fopr_col].iloc[0])
        kpis["field_final_oil_rate"] = float(df[fopr_col].iloc[-1])
        kpis["field_avg_oil_rate"] = float(df[fopr_col].mean())

    # Field oil recovery: use FOPT if available, else sum WOPT:*
    if foip_col and len(df) > 0:
        oil_rec = float(df[foip_col].iloc[-1])
        kpis["field_oil_recovery"] = oil_rec
        kpis["fopt_recovery"] = oil_rec  # FOPT-based alias
    else:
        # Sum well-level cumulative oil
        woip_sum = 0.0
        for col in well_cols:
            if col.startswith('WOPT:'):
                if len(df) > 0:
                    woip_sum += float(df[col].iloc[-1])
        kpis["field_oil_recovery"] = woip_sum
        kpis["fopt_recovery"] = woip_sum

    # Field water recovery: use FWPT if available, else sum WWPT:*
    if fwpt_col and len(df) > 0:
        water_rec = float(df[fwpt_col].iloc[-1])
        kpis["field_water_recovery"] = water_rec
        kpis["fwpt_recovery"] = water_rec  # FWPT-based alias
    else:
        wwpt_sum = 0.0
        for col in well_cols:
            if col.startswith('WWPT:'):
                if len(df) > 0:
                    wwpt_sum += float(df[col].iloc[-1])
        kpis["field_water_recovery"] = wwpt_sum
        kpis["fwpt_recovery"] = wwpt_sum

    # Field gas recovery: use FGPT if available, else sum WGPT:*
    if fgpt_col and len(df) > 0:
        gas_rec = float(df[fgpt_col].iloc[-1])
        kpis["field_gas_recovery"] = gas_rec
        kpis["fgpt_recovery"] = gas_rec  # FGPT-based alias
    else:
        wgpt_sum = 0.0
        for col in well_cols:
            if col.startswith('WGPT:'):
                if len(df) > 0:
                    wgpt_sum += float(df[col].iloc[-1])
        kpis["field_gas_recovery"] = wgpt_sum
        kpis["fgpt_recovery"] = wgpt_sum

    # Field GOR
    if fg_or_col and len(df) > 0:
        kpis["avg_gor"] = float(df[fg_or_col].mean())
        kpis["final_gor"] = float(df[fg_or_col].iloc[-1])

    # Water cut analysis
    wc_data = _compute_watercut(df)
    if wc_data is not None:
        wc_series, wc_col = wc_data
        kpis["max_watercut"] = _sanitize_float(float(wc_series.max()))
        kpis["final_watercut"] = _sanitize_float(float(wc_series.iloc[-1]))
        kpis["avg_watercut"] = _sanitize_float(float(wc_series.mean()))

        # Water breakthrough (first time WC > 1%)
        bt_mask = wc_series > 0.01
        if bt_mask.any():
            bt_idx = bt_mask.idxmax()
            kpis["water_breakthrough_day"] = float(df.loc[bt_idx, 'TIME'])
        else:
            kpis["water_breakthrough_day"] = None
    else:
        # No water production - watercut is 0
        kpis["max_watercut"] = 0.0
        kpis["final_watercut"] = 0.0
        kpis["avg_watercut"] = 0.0
        kpis["water_breakthrough_day"] = None

    # Oil plateau duration (days with rate >= 90% of initial)
    if fopr_col and len(df) > 1:
        initial_rate = df[fopr_col].iloc[0]
        if initial_rate > 0:
            plateau_mask = df[fopr_col] >= 0.9 * initial_rate
            plateau_days = df.loc[plateau_mask, 'TIME']
            if len(plateau_days) > 0:
                kpis["plateau_duration_days"] = float(plateau_days.max() - plateau_days.min())
            else:
                kpis["plateau_duration_days"] = 0.0
    else:
        kpis["plateau_duration_days"] = 0.0

    # Sweep efficiency placeholder (0.0 if pore volume not known)
    kpis["sweep_efficiency"] = 0.0

    # Well-level KPIs
    producer_cols = [c for c in well_cols if _is_producer(c)]
    # Filter to only actual producers (positive oil production)
    well_names = set(c.split(':')[-1] for c in producer_cols)
    actual_producers = [w for w in well_names if _is_producer_well(df, w)]
    kpis["producer_count"] = len(actual_producers)

    for well_name in actual_producers:

        woip = _find_col(df, f'WOPT:{well_name}')
        wopr = _find_col(df, f'WOPR:{well_name}')
        wwpt = _find_col(df, f'WWPT:{well_name}')
        wwpr = _find_col(df, f'WWPR:{well_name}')
        wgpt = _find_col(df, f'WGPT:{well_name}')
        wgpr = _find_col(df, f'WGPR:{well_name}')
        wbhp = _find_col(df, f'WBHP:{well_name}')

        if wopr and len(df) > 0:
            kpis[f"{well_name}_initial_oil_rate"] = float(df[wopr].iloc[0])
            kpis[f"{well_name}_final_oil_rate"] = float(df[wopr].iloc[-1])
            kpis[f"{well_name}_avg_oil_rate"] = float(df[wopr].mean())

        if woip and len(df) > 0:
            kpis[f"{well_name}_cum_oil"] = float(df[woip].iloc[-1])

        if wwpt and len(df) > 0:
            kpis[f"{well_name}_cum_water"] = float(df[wwpt].iloc[-1])

        if wgpt and len(df) > 0:
            kpis[f"{well_name}_cum_gas"] = float(df[wgpt].iloc[-1])

        if wbhp and len(df) > 0:
            kpis[f"{well_name}_final_bhp"] = float(df[wbhp].iloc[-1])
            kpis[f"{well_name}_avg_bhp"] = float(df[wbhp].mean())

        # Well watercut (fraction 0-1)
        if wopr and wwpr and len(df) > 0:
            liq_rate = df[wopr] + df[wwpr]
            # Handle -0.0 in water rate by using absolute value
            wwpr_pos = df[wwpr].abs()
            wc = wwpr_pos / liq_rate.replace(0, np.nan)
            kpis[f"{well_name}_max_watercut"] = _sanitize_float(float(wc.max()))
            kpis[f"{well_name}_final_watercut"] = _sanitize_float(float(wc.iloc[-1]))

        # Well GOR
        if wopr and wgpr and len(df) > 0:
            gor = df[wgpr] / df[wopr].replace(0, np.nan)
            kpis[f"{well_name}_avg_gor"] = _sanitize_float(float(gor.mean()))
            kpis[f"{well_name}_final_gor"] = _sanitize_float(float(gor.iloc[-1]))

    # Recovery factor estimate (if we have FOPT)
    if foip_col and len(df) > 0:
        kpis["recovery_factor"] = float(df[foip_col].iloc[-1]) / 1e6  # rough STB to MMSTB

    # Sanitize: replace any NaN or inf float values with None
    _sanitize_kpis(kpis)

    return kpis


def _sanitize_kpis(kpis: dict[str, Any]) -> None:
    """Replace NaN/inf float values with None in-place to allow JSON serialization."""
    for key, value in list(kpis.items()):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            kpis[key] = None


def _find_col(df: pd.DataFrame, pattern: str) -> str | None:
    """Find column matching pattern (prefix)."""
    for col in df.columns:
        if col.startswith(pattern) or col == pattern:
            return col
    return None


def _is_producer(col: str) -> bool:
    """Check if column belongs to a producer well."""
    # Producers typically have WOPT, WOPR, WWPT, WWPR
    # But we need to distinguish from injectors (INJ) which may have zero rates
    return any(prefix in col for prefix in ['WOPR:', 'WOPT:', 'WWPR:', 'WWPT:'])


def _is_producer_well(df: pd.DataFrame, well_name: str) -> bool:
    """Check if a well is a producer (has positive oil production)."""
    wopr_col = _find_col(df, f'WOPR:{well_name}')
    woip_col = _find_col(df, f'WOPT:{well_name}')
    if wopr_col and len(df) > 0:
        # Check if well has positive oil production
        if df[wopr_col].max() > 0:
            return True
    if woip_col and len(df) > 0:
        # Check cumulative oil
        if df[woip_col].iloc[-1] > 0:
            return True
    return False


def _compute_watercut(df: pd.DataFrame) -> tuple[pd.Series, str] | None:
    """Compute field water cut from field rates."""
    fopr = _find_col(df, 'FOPR')
    fwpr = _find_col(df, 'FWPR')
    if fopr and fwpr and len(df) > 0:
        liq = df[fopr] + df[fwpr]
        # Handle -0.0 in water rate
        fwpr_pos = df[fwpr].clip(lower=0)
        wc = fwpr_pos / liq.replace(0, np.nan)
        return wc, 'FIELD_WC'
    return None