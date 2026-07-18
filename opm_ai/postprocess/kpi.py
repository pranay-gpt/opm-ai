"""KPI extraction from simulation results."""

from typing import Any

import numpy as np
import pandas as pd


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
        - max_watercut: maximum water cut observed
        - breakthrough_day: day when watercut first exceeds threshold
        - plateau_days: days with oil rate above 90% of initial
        - avg_gor: average GOR over simulation
        - sweep_efficiency: estimated sweep efficiency
        - well_count: number of producing wells
        - For each producer: woe, wwe, gwe, cumulative rates, final rates
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

    if foip_col and len(df) > 0:
        kpis["field_oil_recovery"] = float(df[foip_col].iloc[-1])
        kpis["field_oil_recovery_final"] = float(df[foip_col].iloc[-1])

    if fwpt_col and len(df) > 0:
        kpis["field_water_recovery"] = float(df[fwpt_col].iloc[-1])

    if fgpt_col and len(df) > 0:
        kpis["field_gas_recovery"] = float(df[fgpt_col].iloc[-1])

    if fg_or_col and len(df) > 0:
        kpis["avg_gor"] = float(df[fg_or_col].mean())
        kpis["final_gor"] = float(df[fg_or_col].iloc[-1])

    # Water cut analysis
    wc_data = _compute_watercut(df)
    if wc_data is not None:
        wc_series, wc_col = wc_data
        kpis["max_watercut"] = float(wc_series.max())
        kpis["final_watercut"] = float(wc_series.iloc[-1])
        kpis["avg_watercut"] = float(wc_series.mean())

        # Water breakthrough (first time WC > 1%)
        bt_mask = wc_series > 0.01
        if bt_mask.any():
            bt_idx = bt_mask.idxmax()
            kpis["water_breakthrough_day"] = float(df.loc[bt_idx, 'TIME'])
        else:
            kpis["water_breakthrough_day"] = None

    # Oil plateau duration (days with rate > 90% of initial)
    if fopr_col and len(df) > 1:
        initial_rate = df[fopr_col].iloc[0]
        if initial_rate > 0:
            plateau_mask = df[fopr_col] >= 0.9 * initial_rate
            plateau_days = df.loc[plateau_mask, 'TIME']
            if len(plateau_days) > 0:
                kpis["plateau_duration_days"] = float(plateau_days.max() - plateau_days.min())
            else:
                kpis["plateau_duration_days"] = 0.0

    # Well-level KPIs
    producer_cols = [c for c in well_cols if _is_producer(c)]
    kpis["producer_count"] = len(producer_cols)

    for well_col in producer_cols:
        well_name = well_col.split(':')[-1]
        prefix = well_col.split(':')[0]

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

        # Well watercut
        if wopr and wwpr and len(df) > 0:
            liq_rate = df[wopr] + df[wwpr]
            wc = df[wwpr] / liq_rate.replace(0, np.nan)
            kpis[f"{well_name}_max_watercut"] = float(wc.max())
            kpis[f"{well_name}_final_watercut"] = float(wc.iloc[-1])

        # Well GOR
        if wopr and wgpr and len(df) > 0:
            gor = df[wgpr] / df[wopr].replace(0, np.nan)
            kpis[f"{well_name}_avg_gor"] = float(gor.mean())
            kpis[f"{well_name}_final_gor"] = float(gor.iloc[-1])

    # Sweep efficiency estimate (if we have pore volume info)
    # This is a simplified estimate: recovery / (1 - Swi) * (poro * vol)
    # For SPE1, we can estimate from WOPT/FOPT ratio if FOPT exists
    if foip_col and len(df) > 0:
        kpis["recovery_factor"] = float(df[foip_col].iloc[-1]) / 1e6  # rough STB to MMSTB

    return kpis


def _find_col(df: pd.DataFrame, pattern: str) -> str | None:
    """Find column matching pattern (prefix)."""
    for col in df.columns:
        if col.startswith(pattern) or col == pattern:
            return col
    return None


def _is_producer(col: str) -> bool:
    """Check if column belongs to a producer well."""
    # Producers typically have WOPT, WOPR, WWPT, WWPR
    return any(prefix in col for prefix in ['WOPR:', 'WOPT:', 'WWPR:', 'WWPT:'])


def _compute_watercut(df: pd.DataFrame) -> tuple[pd.Series, str] | None:
    """Compute field water cut from field rates."""
    fopr = _find_col(df, 'FOPR')
    fwpr = _find_col(df, 'FWPR')
    if fopr and fwpr and len(df) > 0:
        liq = df[fopr] + df[fwpr]
        wc = df[fwpr] / liq.replace(0, np.nan)
        return wc, 'FIELD_WC'
    return None