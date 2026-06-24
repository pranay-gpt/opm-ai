# opm_ai/preprocess/pvt_builder.py
"""
High-level PVT table builders.

Each function takes a fluid input dataclass and returns a PVTTableResult
with both the numeric table and the ready-to-paste OPM PROPS block.

Units: OPM METRIC mode throughout.
  Pressure  : bar
  FVF       : Rm³/Sm³
  Viscosity : cP
  GOR       : Sm³/Sm³  (converted from scf/STB internally)
"""
import math
from .models import (
    OilFluidInput, WaterFluidInput, GasFluidInput,
    PVTPoint, PVTTableResult, CorrelationMethod,
)
from .pvt_correlations import (
    bar_to_psia, celsius_to_fahrenheit, celsius_to_rankine,
    api_to_sg,
    bo_standing, bo_vasquez_beggs, bo_al_marhoun,
    visc_dead_oil_beggs_robinson, visc_saturated_oil_beggs_robinson,
    pseudo_critical_props, z_factor_papay, bg_rm3_sm3,
    visc_gas_lee_gonzalez,
    bw_meehan, visc_water_kestin, cw_osif,
)


# ──────────────────────────────────────────────────────────────────
# Unit constants
# ──────────────────────────────────────────────────────────────────
_SCF_STB_TO_SM3_SM3 = 0.17811   # 1 scf/STB = 0.17811 Sm³/Sm³
_RB_STB_TO_RM3_SM3  = 0.158987  # 1 RB/STB  = 1 Rm³/Sm³ (same ratio)


# ──────────────────────────────────────────────────────────────────
# Oil PVT  →  PVTO block
# ──────────────────────────────────────────────────────────────────

def build_pvto(inp: OilFluidInput) -> PVTTableResult:
    """
    Generate a PVTO table (live oil) from OilFluidInput.

    Returns a PVTTableResult with:
    - numeric PVTPoint list
    - ready-to-paste OPM PVTO block (METRIC units)
    """
    t_f  = celsius_to_fahrenheit(inp.t_reservoir_c)
    t_r  = celsius_to_rankine(inp.t_reservoir_c)
    sg_o = api_to_sg(inp.api_gravity)
    mw_g = 28.97 * inp.gas_gravity   # approximate molecular weight of gas
    warnings = []

    # Pressure points: below bubble point (saturated) + above (undersaturated)
    p_step = (inp.p_bubble_bar - inp.p_min_bar) / max(inp.n_points - 2, 1)
    pressures_sat = [
        inp.p_min_bar + i * p_step
        for i in range(inp.n_points - 1)
    ] + [inp.p_bubble_bar]
    pressures_sat = sorted(set(round(p, 2) for p in pressures_sat))

    # Rs scales linearly with pressure below bubble point (simplification)
    points   : list[PVTPoint] = []
    opm_lines: list[str]      = []

    for p_bar in pressures_sat:
        # Solution GOR: linear from 0 at p_min to gor_max at bubble point
        rs_scf_stb = inp.gor_scf_stb * (p_bar - inp.p_min_bar) / max(
            inp.p_bubble_bar - inp.p_min_bar, 1
        )
        rs_sm3_sm3 = rs_scf_stb * _SCF_STB_TO_SM3_SM3

        # Bo
        if inp.bo_method == CorrelationMethod.STANDING:
            bo_rb = bo_standing(rs_scf_stb, inp.gas_gravity, inp.api_gravity, t_f)
        elif inp.bo_method == CorrelationMethod.AL_MARHOUN:
            bo_rb = bo_al_marhoun(rs_scf_stb, inp.gas_gravity, sg_o, t_r)
        else:  # VASQUEZ_BEGGS default
            bo_rb = bo_vasquez_beggs(rs_scf_stb, inp.gas_gravity, inp.api_gravity, t_f)

        # Viscosity
        mu_d  = visc_dead_oil_beggs_robinson(inp.api_gravity, t_f)
        mu_o  = visc_saturated_oil_beggs_robinson(mu_d, rs_scf_stb)

        points.append(PVTPoint(
            pressure_bar=p_bar,
            fvf=bo_rb,
            viscosity_cp=mu_o,
            rs_scf_stb=rs_scf_stb,
        ))
        opm_lines.append(
            f"  {rs_sm3_sm3:8.4f}  {p_bar:8.2f}  {bo_rb:8.5f}  {mu_o:8.5f}"
        )

    # Undersaturated point (above bubble point — Bo decreases)
    p_above = inp.p_max_bar
    # Undersaturated Bo correction (linear compression above Pb)
    co = 15e-5  # 1/bar typical oil compressibility
    bo_us = points[-1].fvf * math.exp(-co * (p_above - inp.p_bubble_bar))
    mu_us = points[-1].viscosity_cp * (p_above / inp.p_bubble_bar) ** 0.1
    rs_max_sm3 = inp.gor_scf_stb * _SCF_STB_TO_SM3_SM3

    # OPM PVTO format: Rs  Pb  Bo  Visc /  (saturated)
    #                      P   Bo  Visc    (undersaturated, same Rs)
    block_lines = ["PVTO"]
    block_lines.append("-- Rs(Sm3/Sm3)  P(bar)    Bo      Visc(cP)")
    for i, (line, pt) in enumerate(zip(opm_lines, points)):
        if i < len(opm_lines) - 1:
            block_lines.append(line + "  /")
        else:
            # Last saturated point: append undersaturated row
            block_lines.append(line)
            block_lines.append(
                f"          {p_above:8.2f}  {bo_us:8.5f}  {mu_us:8.5f}  /"
            )
    block_lines.append("/")
    block_lines.append("")

    return PVTTableResult(
        table_type="PVTO",
        points=points,
        opm_block="\n".join(block_lines),
        correlation_used=f"Bo: {inp.bo_method.value}, Visc: Beggs-Robinson",
        warnings=warnings,
    )


# ──────────────────────────────────────────────────────────────────
# Water PVT  →  PVTW block
# ──────────────────────────────────────────────────────────────────

def build_pvtw(inp: WaterFluidInput) -> PVTTableResult:
    """
    Generate a PVTW block (single-row reference point) from WaterFluidInput.
    OPM PVTW format:  P_REF  Bw  Cw  Visc  Viscosibility
    """
    bw   = bw_meehan(inp.p_ref_bar, inp.t_reservoir_c)
    cw   = cw_osif(inp.p_ref_bar, inp.t_reservoir_c, inp.salinity_ppm)
    visc = visc_water_kestin(inp.t_reservoir_c, inp.salinity_ppm)

    block = (
        f"PVTW\n"
        f"-- P_REF(bar)  Bw(Rm3/Sm3)  Cw(1/bar)    Visc(cP)  Viscosibility\n"
        f"  {inp.p_ref_bar:.2f}  {bw:.5f}  {cw:.3e}  {visc:.5f}  0 /\n"
    )

    return PVTTableResult(
        table_type="PVTW",
        points=[PVTPoint(
            pressure_bar=inp.p_ref_bar,
            fvf=bw,
            viscosity_cp=visc,
        )],
        opm_block=block,
        correlation_used="Bw: Meehan (1980), Visc: Kestin (1978), Cw: Osif (1988)",
    )


# ──────────────────────────────────────────────────────────────────
# Gas PVT  →  PVDG block
# ──────────────────────────────────────────────────────────────────

def build_pvdg(inp: GasFluidInput) -> PVTTableResult:
    """
    Generate a PVDG table (dry gas) from GasFluidInput.
    OPM PVDG format:  P(bar)  Bg(Rm3/Sm3)  Visc(cP)
    """
    t_r  = celsius_to_rankine(inp.t_reservoir_c)
    mw_g = 28.97 * inp.gas_gravity
    warnings = []

    p_step = (inp.p_max_bar - inp.p_min_bar) / max(inp.n_points - 1, 1)
    pressures = [inp.p_min_bar + i * p_step for i in range(inp.n_points)]

    points:     list[PVTPoint] = []
    opm_lines:  list[str]      = []

    for p_bar in pressures:
        p_psia = bar_to_psia(p_bar)
        z      = z_factor_papay(p_psia, t_r, inp.gas_gravity)
        bg     = bg_rm3_sm3(p_bar, inp.t_reservoir_c, z)
        mu_g   = visc_gas_lee_gonzalez(p_psia, t_r, mw_g, z)

        points.append(PVTPoint(
            pressure_bar=p_bar,
            fvf=bg,
            viscosity_cp=mu_g,
        ))
        opm_lines.append(f"  {p_bar:8.2f}  {bg:.6f}  {mu_g:.5f}")

    block_lines = [
        "PVDG",
        "-- P(bar)     Bg(Rm3/Sm3)  Visc(cP)",
    ]
    block_lines.extend(opm_lines)
    block_lines.append("/")
    block_lines.append("")

    return PVTTableResult(
        table_type="PVDG",
        points=points,
        opm_block="\n".join(block_lines),
        correlation_used="Z: Papay (1985), Bg: ideal gas law, Visc: Lee-Gonzalez-Eakin (1966)",
        warnings=warnings,
    )
