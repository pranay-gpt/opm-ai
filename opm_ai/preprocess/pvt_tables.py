# opm_ai/preprocess/pvt_tables.py
"""
Per-fluid PVT table builders.

Public functions
----------------
build_pvto(inp: OilFluidInput)   -> PVTTableResult
build_pvtw(inp: WaterFluidInput) -> PVTTableResult
build_pvdg(inp: GasFluidInput)   -> PVTTableResult

Each function:
  1. Resolves input defaults
  2. Calls the appropriate correlation(s) from pvt_correlations.py
  3. Returns a PVTTableResult with a fully formatted OPM keyword block

All outputs are in OPM METRIC units:
  Pressure        : bar
  FVF (liquid)    : Rm³/Sm³
  FVF (gas)       : Rm³/Sm³
  Viscosity       : cP
  Compressibility : 1/bar
  GOR             : Sm³/Sm³  (1 SCF/STB = 0.17811 Sm³/Sm³)
"""
from __future__ import annotations
import math

from .pvt_models import (
    OilFluidInput, WaterFluidInput, GasFluidInput,
    PVTTableResult, PVTPoint, CorrelationMethod,
)
from .pvt_correlations import (
    # unit helpers
    bar_to_psia, celsius_to_fahrenheit, celsius_to_rankine, api_to_sg,
    # oil
    bo_standing, bo_vasquez_beggs, bo_al_marhoun,
    visc_dead_oil_beggs_robinson, visc_saturated_oil_beggs_robinson,
    # gas
    z_factor_papay, bg_rm3_sm3, visc_gas_lee_gonzalez,
    # water
    bw_meehan, visc_water_kestin, cw_osif,
)

_SCF_STB_TO_SM3_SM3 = 0.17811   # unit conversion


# ── PVTO ─────────────────────────────────────────────────────────────────────

def build_pvto(inp: OilFluidInput) -> PVTTableResult:
    """
    Build a saturated PVTO table.

    The table spans from inp.p_min_bar up to max(p_bubble_bar, p_max_bar)
    with inp.n_points rows.  Rs is scaled linearly from 0 at p_min to
    inp.gor_scf_stb at inp.p_bubble_bar.
    """
    p_max = inp.p_max_bar if inp.p_max_bar is not None else inp.p_bubble_bar * 1.30
    pressures = _linspace(inp.p_min_bar, inp.p_bubble_bar, inp.n_points)

    t_f  = celsius_to_fahrenheit(inp.t_reservoir_c)
    t_r  = celsius_to_rankine(inp.t_reservoir_c)
    sg_o = api_to_sg(inp.api_gravity)

    # Rs scales linearly with pressure (0 at p_min → gor at p_bubble)
    rs_at_p = lambda p: inp.gor_scf_stb * (p - inp.p_min_bar) / max(inp.p_bubble_bar - inp.p_min_bar, 1.0)

    points: list[PVTPoint] = []
    for p_bar in pressures:
        p_psia = bar_to_psia(p_bar)
        rs_scf = max(rs_at_p(p_bar), 0.0)
        rs_si  = rs_scf * _SCF_STB_TO_SM3_SM3

        if inp.bo_method == CorrelationMethod.AL_MARHOUN:
            bo = bo_al_marhoun(
                rs_scf_stb=rs_scf, sg_gas=inp.sg_gas,
                sg_oil=sg_o, t_rankine=t_r,
            )
            method_name = "Al-Marhoun (1988)"
        elif inp.bo_method == CorrelationMethod.VASQUEZ_BEGGS:
            bo = bo_vasquez_beggs(
                rs_scf_stb=rs_scf, sg_gas=inp.sg_gas,
                api=inp.api_gravity, t_f=t_f,
            )
            method_name = "Vasquez-Beggs (1980)"
        else:  # default Standing
            bo = bo_standing(
                rs_scf_stb=rs_scf, sg_gas=inp.sg_gas,
                api=inp.api_gravity, t_f=t_f,
            )
            method_name = "Standing (1947)"

        mu_dead = visc_dead_oil_beggs_robinson(api=inp.api_gravity, t_f=t_f)
        mu_sat  = visc_saturated_oil_beggs_robinson(mu_dead=mu_dead, rs_scf_stb=rs_scf)

        points.append(PVTPoint(
            pressure_bar=round(p_bar, 2),
            fvf=round(bo, 5),
            viscosity_cp=round(mu_sat, 4),
            rs_sm3_sm3=round(rs_si, 4),
        ))

    opm_block = _format_pvto(points)
    return PVTTableResult(
        table_type="PVTO",
        opm_block=opm_block,
        points=points,
        correlation_used=f"{method_name} Bo + Beggs-Robinson (1975) visc",
    )


# ── PVTW ─────────────────────────────────────────────────────────────────────

def build_pvtw(inp: WaterFluidInput) -> PVTTableResult:
    """
    Build a PVTW single-row record.

    PVTW format (OPM METRIC):
      P_ref [bar]  Bw [Rm³/Sm³]  Cw [1/bar]  visc [cP]  viscosibility /
    """
    bw     = bw_meehan(p_bar=inp.p_ref_bar, t_c=inp.t_reservoir_c)
    cw     = cw_osif(p_bar=inp.p_ref_bar, t_c=inp.t_reservoir_c, salinity_ppm=inp.salinity_ppm)
    visc_w = visc_water_kestin(t_c=inp.t_reservoir_c, salinity_ppm=inp.salinity_ppm)

    point = PVTPoint(
        pressure_bar=inp.p_ref_bar,
        fvf=round(bw, 5),
        viscosity_cp=round(visc_w, 4),
    )

    opm_block = (
        f"PVTW\n"
        f"--  P_ref [bar]  Bw [Rm3/Sm3]  Cw [1/bar]      visc [cP]  vsrb\n"
        f"  {inp.p_ref_bar:.1f}  {bw:.5f}  {cw:.3e}  {visc_w:.4f}  0 /\n"
    )

    return PVTTableResult(
        table_type="PVTW",
        opm_block=opm_block,
        points=[point],
        correlation_used="Meehan (1980) Bw + Osif (1988) Cw + Kestin (1978) visc",
    )


# ── PVDG ─────────────────────────────────────────────────────────────────────

def build_pvdg(inp: GasFluidInput) -> PVTTableResult:
    """
    Build a PVDG table (dry gas or gas-cap).

    PVDG format (OPM METRIC):
      P [bar]  Bg [Rm³/Sm³]  visc [cP]
    """
    t_r    = celsius_to_rankine(inp.t_reservoir_c)
    mw_gas = 28.97 * inp.gas_gravity
    pressures = _linspace(inp.p_min_bar, inp.p_max_bar, inp.n_points)

    points: list[PVTPoint] = []
    for p_bar in pressures:
        p_psia = bar_to_psia(p_bar)
        z      = z_factor_papay(
            p_psia=p_psia, t_rankine=t_r, sg_gas=inp.gas_gravity,
        )
        bg     = bg_rm3_sm3(p_bar=p_bar, t_c=inp.t_reservoir_c, z=z)
        mu_g   = visc_gas_lee_gonzalez(
            p_psia=p_psia, t_rankine=t_r, mw_gas=mw_gas, z=z,
        )
        points.append(PVTPoint(
            pressure_bar=round(p_bar, 2),
            fvf=round(bg, 6),
            viscosity_cp=round(mu_g, 5),
            z_factor=round(z, 4),
        ))

    opm_block = _format_pvdg(points)
    return PVTTableResult(
        table_type="PVDG",
        opm_block=opm_block,
        points=points,
        correlation_used="Papay (1985) Z-factor + Lee-Gonzalez-Eakin (1966) visc",
    )


# ── OPM block formatters ─────────────────────────────────────────────────────

def _format_pvto(points: list[PVTPoint]) -> str:
    lines = [
        "PVTO",
        "--  Rs [Sm3/Sm3]  P [bar]  Bo [Rm3/Sm3]  visc [cP]",
    ]
    for pt in points:
        lines.append(
            f"  {pt.rs_sm3_sm3:.4f}  {pt.pressure_bar:.2f}"
            f"  {pt.fvf:.5f}  {pt.viscosity_cp:.4f}"
        )
    lines.append("/")
    lines.append("/")
    return "\n".join(lines) + "\n"


def _format_pvdg(points: list[PVTPoint]) -> str:
    lines = [
        "PVDG",
        "--  P [bar]  Bg [Rm3/Sm3]  visc [cP]",
    ]
    for pt in points:
        lines.append(
            f"  {pt.pressure_bar:.2f}  {pt.fvf:.6f}  {pt.viscosity_cp:.5f}"
        )
    lines.append("/")
    return "\n".join(lines) + "\n"


# ── Helper ───────────────────────────────────────────────────────────────────

def _linspace(start: float, stop: float, n: int) -> list[float]:
    """Return n evenly-spaced values from start to stop inclusive."""
    if n == 1:
        return [start]
    step = (stop - start) / (n - 1)
    return [start + i * step for i in range(n)]
