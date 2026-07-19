"""Table builders and renderers for OPM PROPS blocks.

Builds PVT and relative permeability tables from fluid descriptors and
renders them as OPM keyword blocks with proper formatting.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np

from opm_ai.preprocess.correlations import (
    almarhoun_bo,
    beggs_robinson_muo_dead,
    beggs_robinson_muo_live,
    corey_sgof,
    corey_swof,
    gas_bg,
    gas_z_papay,
    lee_gonzalez_mug,
    let_sgof,
    let_swof,
    mccain_bw,
    mccain_muw,
    standing_bo,
    standing_rs_bubble,
    vasquez_beggs_bo,
)
from opm_ai.preprocess.models import FluidDescriptor


UnitSystem = Literal["FIELD", "METRIC"]


# ============================================================================
# Table Builders
# ============================================================================

def build_pvt_oil_table(
    fluid: FluidDescriptor,
    correlation: str,
    endpoints: dict[str, float],
) -> list[dict]:
    """
    Build PVTO table rows with keys: RS, P, BO, MUO.

    Saturated section: ~8 pressure nodes from p_min to Pb.
    Undersaturated extension: at max Rs for p up to ~1.8*p_max.
    """
    p_min, p_max = fluid.pressure_range
    temp_f = fluid.temp_f
    api = fluid.api_gravity
    gas_grav = fluid.gas_specific_gravity
    gor = fluid.gor

    # Compute Rs at reservoir conditions (initial pressure = p_max)
    rs_res, pb = standing_rs_bubble(api, gas_grav, temp_f, p_max)

    # Use provided GOR if it's less than computed Rs (undersaturated)
    if gor < rs_res:
        rs_res = gor
        # Recompute bubble point for the capped Rs
        # Invert Standing: Pb = 18.2 * ((Rs/gas_grav)^0.83 * 10^(0.00091*T - 0.0125*API) - 1.4)
        inv_term = 10 ** (0.00091 * temp_f - 0.0125 * api)
        pb = 18.2 * ((rs_res / gas_grav) ** 0.83 * inv_term - 1.4)
        pb = max(pb, 0.0)

    # Saturated section: ~8 points from p_min to pb
    n_sat = 8
    p_sat = np.linspace(p_min, pb, n_sat)
    # Ensure Rs is non-decreasing with pressure
    rs_sat = np.array([standing_rs_bubble(api, gas_grav, temp_f, p)[0] for p in p_sat])
    # Ensure Rs non-decreasing (Standing should be monotonic but ensure)
    rs_sat = np.maximum.accumulate(rs_sat)

    # Cap at max Rs (gor or rs_res)
    rs_max = min(gor, rs_res)
    rs_sat = np.minimum(rs_sat, rs_max)

    rows = []
    for p, rs in zip(p_sat, rs_sat):
        # Compute Bo
        if correlation == "Standing":
            bo = standing_bo(api, gas_grav, temp_f, rs)
        elif correlation == "VasquezBeggs":
            bo = vasquez_beggs_bo(api, gas_grav, temp_f, rs)
        elif correlation == "AlMarhoun":
            bo = almarhoun_bo(api, gas_grav, temp_f, rs, p)
        else:
            bo = standing_bo(api, gas_grav, temp_f, rs)

        # Compute oil viscosity
        mu_od = beggs_robinson_muo_dead(api, temp_f)
        muo = beggs_robinson_muo_live(mu_od, rs)

        rows.append({
            "RS": float(rs),
            "P": float(p),
            "BO": float(bo),
            "MUO": float(muo),
        })

    # Undersaturated extension at max Rs for p > pb up to ~1.8 * p_max
    if pb < p_max:
        p_unsat = np.linspace(pb, min(p_max * 1.8, 1.5 * p_max), 4)[1:]  # skip pb duplicate
        co = 1e-5  # oil compressibility 1/psi
        bo_pb = rows[-1]["BO"]
        muo_pb = rows[-1]["MUO"]

        for p in p_unsat:
            # Undersaturated Bo: Bo = Bo_b * exp(-co * (p - pb))
            bo = bo_pb * math.exp(-co * (p - pb))
            # Undersaturated viscosity: mu = mu_b * (p/pb)^0.2
            muo = muo_pb * (p / pb) ** 0.2
            rows.append({
                "RS": float(rs_max),
                "P": float(p),
                "BO": float(bo),
                "MUO": float(muo),
            })

    return rows


def build_pvdg_table(
    fluid: FluidDescriptor,
) -> list[dict]:
    """
    Build PVDG table rows with keys: P, BG, MUG.

    ~10 pressure nodes from p_min to p_max. Pressure strictly increasing.
    BG strictly decreasing.
    """
    p_min, p_max = fluid.pressure_range
    temp_f = fluid.temp_f
    gas_grav = fluid.gas_specific_gravity

    n_points = 10
    p_nodes = np.linspace(p_min, p_max, n_points)

    rows = []
    for p in p_nodes:
        bg = gas_bg(p, temp_f, gas_grav)
        mug = lee_gonzalez_mug(p, temp_f, gas_grav)
        rows.append({
            "P": float(p),
            "BG": float(bg),
            "MUG": float(mug),
        })

    return rows


def build_pvt_water_table(
    fluid: FluidDescriptor,
) -> list[dict]:
    """
    Build PVTW table - single row at reference pressure (p_max midpoint).

    Keys: P, BW, CW, MUW, VISCO (viscosibility = 0 for now).
    """
    p_min, p_max = fluid.pressure_range
    p_ref = (p_min + p_max) / 2.0
    temp_f = fluid.temp_f
    salinity = fluid.salinity_ppm

    bw = mccain_bw(p_ref, temp_f)
    muw = mccain_muw(temp_f, salinity)
    cw = 3.0e-6  # water compressibility 1/psi
    viscosibility = 0.0

    return [{
        "P": float(p_ref),
        "BW": float(bw),
        "CW": float(cw),
        "MUW": float(muw),
        "VISCO": float(viscosibility),
    }]


def build_rock_table(
    fluid: FluidDescriptor,
) -> list[dict]:
    """
    Build ROCK table - single row at p_min with compressibility.

    Keys: P, CR (rock compressibility 1/psi).
    """
    p_min, _ = fluid.pressure_range
    cr = 3.0e-6  # rock compressibility 1/psi

    return [{
        "P": float(p_min),
        "CR": float(cr),
    }]


def build_density_table(
    fluid: FluidDescriptor,
) -> dict[str, float]:
    """
    Build surface densities for DENSITY block.

    Keys: OIL, WATER, GAS (in lb/ft3 for FIELD, kg/m3 for METRIC).
    """
    api = fluid.api_gravity
    gas_grav = fluid.gas_specific_gravity
    salinity = fluid.salinity_ppm

    # Oil density at surface conditions (lb/ft3)
    oil_density = 62.428 * 141.5 / (131.5 + api)

    # Water density at surface (lb/ft3) - approximate with salinity
    water_density = 62.428 * (1.0 + salinity * 0.695e-6)

    # Gas density at standard conditions (lb/ft3)
    # Air at SC: 0.0765 lb/ft3
    gas_density = 0.0765 * gas_grav

    return {
        "OIL": float(oil_density),
        "WATER": float(water_density),
        "GAS": float(gas_density),
    }


def build_swof_table(
    fluid: FluidDescriptor,
    endpoints: dict[str, float],
    correlation: str,
) -> list[dict]:
    """
    Build SWOF table rows with keys: SW, KRW, KRO, PCOW.

    ~12 rows from Swc to 1.0. Sw strictly increasing.
    Pcow = 0 for now.
    """
    swc = endpoints.get("swc", 0.12)
    sorw = endpoints.get("sorw", 0.20)
    krw_max = endpoints.get("krw_max", 0.50)
    kro_max = endpoints.get("kro_max", 1.0)
    nw = endpoints.get("nw", 2.0)
    no = endpoints.get("no", 2.0)
    l_w = endpoints.get("l_w", 2.0)
    e_w = endpoints.get("e_w", 1.0)
    t_w = endpoints.get("t_w", 2.0)
    l_o = endpoints.get("l_o", 2.0)
    e_o = endpoints.get("e_o", 1.0)
    t_o = endpoints.get("t_o", 2.0)

    n_points = 12
    s_max = 1.0 - sorw
    sw_nodes = np.linspace(swc, s_max, n_points - 1)
    # Add Sw=1.0 as final point
    sw_nodes = np.append(sw_nodes, 1.0)

    rows = []
    for sw in sw_nodes:
        if correlation == "LET":
            krw, kro = let_swof(
                sw, swc, sorw, krw_max, kro_max,
                l_w, e_w, t_w, l_o, e_o, t_o
            )
        else:  # Corey
            krw, kro = corey_swof(
                sw, swc, sorw, krw_max, kro_max, nw, no
            )

        rows.append({
            "SW": float(sw),
            "KRW": float(krw),
            "KRO": float(kro),
            "PCOW": 0.0,
        })

    return rows


def build_sgof_table(
    fluid: FluidDescriptor,
    endpoints: dict[str, float],
    correlation: str,
) -> list[dict]:
    """
    Build SGOF table rows with keys: SG, KRG, KRO, PCOG.

    ~12 rows from 0 to 1-swc-sorg. Sg strictly increasing.
    Pcog = 0 for now.
    """
    swc = endpoints.get("swc", 0.12)
    sorg = endpoints.get("sorg", 0.05)
    sgc = endpoints.get("sgc", 0.0)
    krg_max = endpoints.get("krg_max", 1.0)
    kro_max = endpoints.get("kro_max", 1.0)
    ng = endpoints.get("ng", 2.0)
    nog = endpoints.get("nog", 2.0)
    l_g = endpoints.get("l_g", 2.0)
    e_g = endpoints.get("e_g", 1.0)
    t_g = endpoints.get("t_g", 2.0)
    l_o = endpoints.get("l_o", 2.0)
    e_o = endpoints.get("e_o", 1.0)
    t_o = endpoints.get("t_o", 2.0)

    n_points = 12
    s_max = 1.0 - swc - sorg
    sg_nodes = np.linspace(0.0, s_max, n_points)

    rows = []
    for sg in sg_nodes:
        if correlation == "LET":
            krg, kro = let_sgof(
                sg, sgc, sorg, swc, krg_max, kro_max,
                l_g, e_g, t_g, l_o, e_o, t_o
            )
        else:  # Corey
            krg, kro = corey_sgof(
                sg, sgc, sorg, swc, krg_max, kro_max, ng, nog
            )

        rows.append({
            "SG": float(sg),
            "KRG": float(krg),
            "KRO": float(kro),
            "PCOG": 0.0,
        })

    return rows


# ============================================================================
# Renderers
# ============================================================================

def _convert_to_metric(value: float, prop_type: str) -> float:
    """Convert FIELD value to METRIC for output."""
    if prop_type == "PRESSURE":  # psia -> bar
        return value * 0.0689476
    elif prop_type == "BG":  # rb/Mscf -> m3/sm3
        return value * 0.0056147
    elif prop_type == "DENSITY":  # lb/ft3 -> kg/m3
        return value * 16.0185
    elif prop_type == "RS":  # scf/stb -> sm3/sm3
        return value * 0.17811
    elif prop_type in ("BO", "BW"):  # rb/stb dimensionless - no change
        return value
    elif prop_type in ("MUO", "MUG", "MUW"):  # cp - no change
        return value
    elif prop_type == "TEMPERATURE":  # degF -> degC
        return (value - 32.0) * 5.0 / 9.0
    return value


def _format_val(val: float, fmt: str = ".6g") -> str:
    """Format a float value with given format."""
    return format(val, fmt)


def render_pvto(
    rows: list[dict],
    fluid: FluidDescriptor,
) -> str:
    """Render PVTO block in OPM format."""
    unit = fluid.unit_system
    lines = ["PVTO"]

    # Group by RS value
    current_rs = None
    group_rows = []

    def flush_group():
        nonlocal current_rs, group_rows
        if not group_rows:
            return
        rs_val = group_rows[0]["RS"]
        if unit == "METRIC":
            rs_val = _convert_to_metric(rs_val, "RS")
        lines.append(f"    {_format_val(rs_val)}")  # RS header
        for row in group_rows:
            p = row["P"]
            bo = row["BO"]
            muo = row["MUO"]
            if unit == "METRIC":
                p = _convert_to_metric(p, "PRESSURE")
                # BO dimensionless, MUO cp unchanged
            lines.append(f"    {_format_val(p)} {_format_val(bo)} {_format_val(muo)}")
        lines.append("    /")  # end of RS group
        group_rows = []

    for row in rows:
        rs = row["RS"]
        if current_rs is None or abs(rs - current_rs) > 1e-6:
            flush_group()
            current_rs = rs
        group_rows.append(row)

    flush_group()
    lines.append("/")  # end of PVTO
    return "\n".join(lines)


def render_pvdg(
    rows: list[dict],
    fluid: FluidDescriptor,
) -> str:
    """Render PVDG block in OPM format."""
    unit = fluid.unit_system
    lines = ["PVDG"]

    for row in rows:
        p = row["P"]
        bg = row["BG"]
        mug = row["MUG"]
        if unit == "METRIC":
            p = _convert_to_metric(p, "PRESSURE")
            bg = _convert_to_metric(bg, "BG")
        lines.append(f"    {_format_val(p)} {_format_val(bg)} {_format_val(mug)}")

    lines.append("/")
    return "\n".join(lines)


def render_pvtw(
    rows: list[dict],
    fluid: FluidDescriptor,
) -> str:
    """Render PVTW block in OPM format."""
    unit = fluid.unit_system
    row = rows[0]  # single row
    p = row["P"]
    bw = row["BW"]
    cw = row["CW"]
    muw = row["MUW"]
    visco = row["VISCO"]

    if unit == "METRIC":
        p = _convert_to_metric(p, "PRESSURE")
        # BW dimensionless, CW 1/bar, MUW cp, VISCO 1/bar
        cw = cw / 0.0689476  # 1/psi -> 1/bar

    lines = [
        "PVTW",
        f"    {_format_val(p)} {_format_val(bw)} {_format_val(cw)} {_format_val(muw)} {_format_val(visco)}",
        "/",
    ]
    return "\n".join(lines)


def render_rock(
    rows: list[dict],
    fluid: FluidDescriptor,
) -> str:
    """Render ROCK block in OPM format."""
    unit = fluid.unit_system
    row = rows[0]
    p = row["P"]
    cr = row["CR"]

    if unit == "METRIC":
        p = _convert_to_metric(p, "PRESSURE")
        cr = cr / 0.0689476  # 1/psi -> 1/bar

    lines = [
        "ROCK",
        f"    {_format_val(p)} {_format_val(cr)}",
        "/",
    ]
    return "\n".join(lines)


def render_density(
    vals: dict[str, float],
    fluid: FluidDescriptor,
) -> str:
    """Render DENSITY block in OPM format."""
    unit = fluid.unit_system
    oil = vals["OIL"]
    water = vals["WATER"]
    gas = vals["GAS"]

    if unit == "METRIC":
        oil = _convert_to_metric(oil, "DENSITY")
        water = _convert_to_metric(water, "DENSITY")
        gas = _convert_to_metric(gas, "DENSITY")

    lines = [
        "DENSITY",
        f"    {_format_val(oil)} {_format_val(water)} {_format_val(gas)}",
        "/",
    ]
    return "\n".join(lines)


def render_swof(
    rows: list[dict],
    fluid: FluidDescriptor,
) -> str:
    """Render SWOF block in OPM format."""
    unit = fluid.unit_system
    lines = ["SWOF"]

    for row in rows:
        sw = row["SW"]
        krw = row["KRW"]
        kro = row["KRO"]
        pcow = row["PCOW"]
        if unit == "METRIC":
            pcow = _convert_to_metric(pcow, "PRESSURE")
        lines.append(f"    {_format_val(sw)} {_format_val(krw)} {_format_val(kro)} {_format_val(pcow)}")

    lines.append("/")
    return "\n".join(lines)


def render_sgof(
    rows: list[dict],
    fluid: FluidDescriptor,
) -> str:
    """Render SGOF block in OPM format."""
    unit = fluid.unit_system
    lines = ["SGOF"]

    for row in rows:
        sg = row["SG"]
        krg = row["KRG"]
        kro = row["KRO"]
        pcog = row["PCOG"]
        if unit == "METRIC":
            pcog = _convert_to_metric(pcog, "PRESSURE")
        lines.append(f"    {_format_val(sg)} {_format_val(krg)} {_format_val(kro)} {_format_val(pcog)}")

    lines.append("/")
    return "\n".join(lines)


