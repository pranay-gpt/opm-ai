# opm_ai/preprocess/pvt_builder.py
"""
PVT Property Builder
--------------------
Translates a ReservoirDescription into a PVTProps dataclass using
physics-based correlations (pvt_correlations.py).

All outputs are in OPM METRIC units:
  Pressure     : bar
  FVF (liquid) : Rm³/Sm³
  FVF (gas)    : Rm³/Sm³
  Viscosity    : cP
  Compressibility: 1/bar
  GOR          : Sm³/Sm³

Fluid system routing:
  oil_water  → PVTW + PVCDO   (dead oil, no gas)
  black_oil  → PVTW + PVTO (saturated table) + PVDG
  gas_water  → PVTW + PVDG
  dry_gas    → PVTW + PVDG (no oil phase)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple

from .pvt_correlations import (
    visc_water_kestin, bw_meehan, cw_osif,
    bo_standing, visc_dead_oil_beggs_robinson,
    visc_saturated_oil_beggs_robinson,
    z_factor_papay, bg_rm3_sm3, visc_gas_lee_gonzalez,
    celsius_to_rankine,
)

# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class PVTProps:
    """
    Computed PVT properties for a single reservoir.
    Tables are lists of (value, ...) tuples matching OPM keyword order.
    """
    # PVTW  ---  P_ref  Bw  Cw  visc_w  vsrb
    pvtw_p_ref  : float
    pvtw_bw     : float
    pvtw_cw     : float
    pvtw_visc   : float

    # PVCDO (dead-oil/oil_water) or None
    pvcdo_bo    : float | None = None
    pvcdo_visc  : float | None = None

    # PVTO table rows [(Rs, [(P, Bo, visc), ...]), ...]
    pvto_rows   : List[Tuple[float, List[Tuple[float, float, float]]]] = field(default_factory=list)

    # PVDG table rows [(P, Bg, visc), ...]
    pvdg_rows   : List[Tuple[float, float, float]] = field(default_factory=list)

    # Surface densities (kg/m3 for METRIC)
    rho_oil     : float = 820.0
    rho_water   : float = 1025.0
    rho_gas     : float = 1.0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_pvt_props(
    p_init_bar  : float,
    t_c         : float,
    fluid_system: str,
    api         : float       = 35.0,
    sg_gas      : float       = 0.65,
    salinity_ppm: float       = 50_000.0,
    n_pvt_points: int         = 8,
) -> PVTProps:
    """
    Compute a full PVTProps for any fluid system.

    Parameters
    ----------
    p_init_bar   : Initial reservoir pressure [bar]
    t_c          : Reservoir temperature [°C]
    fluid_system : 'oil_water' | 'black_oil' | 'gas_water' | 'dry_gas'
    api          : Oil API gravity (used for oil-bearing systems)
    sg_gas       : Gas specific gravity (used for gas-bearing systems)
    salinity_ppm : Brine salinity [ppm NaCl]
    n_pvt_points : Number of pressure points in PVT tables
    """
    # ---- Water (all systems) -----------------------------------------------
    bw   = bw_meehan(p_init_bar, t_c)
    cw   = cw_osif(p_init_bar, t_c, salinity_ppm)
    visc_w = visc_water_kestin(t_c, salinity_ppm)

    props = PVTProps(
        pvtw_p_ref=p_init_bar,
        pvtw_bw=bw,
        pvtw_cw=cw,
        pvtw_visc=visc_w,
    )

    t_f  = t_c * 9/5 + 32
    t_r  = celsius_to_rankine(t_c)

    # ---- Oil_water (dead oil) -----------------------------------------------
    if fluid_system == "oil_water":
        bo   = bo_standing(rs_scf_stb=0.0, sg_gas=sg_gas, api=api, t_f=t_f)
        mu_d = visc_dead_oil_beggs_robinson(api=api, t_f=t_f)
        props.pvcdo_bo   = bo
        props.pvcdo_visc = mu_d
        props.rho_oil    = _api_to_density(api)
        return props

    # ---- Black oil (saturated PVTO + PVDG) ----------------------------------
    if fluid_system == "black_oil":
        props.rho_oil = _api_to_density(api)
        props.rho_gas = sg_gas * 1.225  # kg/m3 at std conditions
        props.pvto_rows = _build_pvto(p_init_bar, t_f, api, sg_gas, n_pvt_points)
        props.pvdg_rows = _build_pvdg(p_init_bar, t_c, t_r, sg_gas, n_pvt_points)
        return props

    # ---- Gas_water / dry_gas ------------------------------------------------
    if fluid_system in ("gas_water", "dry_gas"):
        props.rho_gas   = sg_gas * 1.225
        props.pvdg_rows = _build_pvdg(p_init_bar, t_c, t_r, sg_gas, n_pvt_points)
        return props

    return props  # fallback — returns water only


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _api_to_density(api: float) -> float:
    """Convert API gravity to stock-tank oil density [kg/m3]."""
    sg = 141.5 / (api + 131.5)
    return sg * 1000.0


def _pressure_range(p_init_bar: float, n: int) -> list[float]:
    """
    Generate n pressure points from ~10% of p_init to 130% of p_init.
    Always includes p_init itself as the last (saturation) point.
    """
    p_min = max(20.0, p_init_bar * 0.10)
    p_max = p_init_bar * 1.30
    step  = (p_max - p_min) / (n - 1)
    pts   = [p_min + i * step for i in range(n - 1)]
    pts.append(p_init_bar)  # ensure p_init is the saturation pressure row
    return sorted(pts)


def _build_pvto(
    p_init_bar : float,
    t_f        : float,
    api        : float,
    sg_gas     : float,
    n          : int,
) -> list[tuple[float, list[tuple[float, float, float]]]]:
    """
    Build PVTO saturated table rows.
    OPM PVTO format:  Rs [Sm3/Sm3]  P [bar]  Bo [Rm3/Sm3]  visc [cP]

    We use a simplified Rs-P relationship:
      Rs = k * P^1.2  (Standing correlation approximation)
    scaled so Rs = rs_max at p_init.
    """
    import math
    rs_max  = 100.0  # Sm3/Sm3 typical for 35 API at 200 bar
    k       = rs_max / (p_init_bar ** 1.2)
    pressures = _pressure_range(p_init_bar, n)
    rows = []
    for p_bar in pressures:
        p_psia = p_bar * 14.5038
        rs     = k * (p_bar ** 1.2)  # Sm3/Sm3 (approx, 1 SCF/STB ~ 0.178 Sm3/Sm3)
        rs_scf = rs * 5.615          # convert Sm3/Sm3 to SCF/STB
        bo     = bo_standing(rs_scf_stb=rs_scf, sg_gas=sg_gas, api=api, t_f=t_f)
        mu_d   = visc_dead_oil_beggs_robinson(api=api, t_f=t_f)
        mu_sat = visc_saturated_oil_beggs_robinson(mu_dead=mu_d, rs_scf_stb=rs_scf)
        rows.append((round(rs, 4), [(round(p_bar, 2), round(bo, 5), round(mu_sat, 4))]))
    return rows


def _build_pvdg(
    p_init_bar : float,
    t_c        : float,
    t_r        : float,
    sg_gas     : float,
    n          : int,
) -> list[tuple[float, float, float]]:
    """
    Build PVDG table rows: P [bar]  Bg [Rm3/Sm3]  visc [cP]
    Uses Papay Z-factor + Lee-Gonzalez viscosity.
    """
    mw_gas    = 28.97 * sg_gas  # g/mol
    pressures = _pressure_range(p_init_bar, n)
    rows = []
    for p_bar in pressures:
        p_psia = p_bar * 14.5038
        z      = z_factor_papay(p_psia=p_psia, t_rankine=t_r, sg_gas=sg_gas)
        bg     = bg_rm3_sm3(p_bar=p_bar, t_c=t_c, z=z)
        mu_g   = visc_gas_lee_gonzalez(p_psia=p_psia, t_rankine=t_r, mw_gas=mw_gas, z=z)
        rows.append((round(p_bar, 2), round(bg, 6), round(mu_g, 5)))
    return rows
