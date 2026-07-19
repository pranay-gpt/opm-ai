"""PVT correlation primitive functions (pure Python + numpy).

Each function is a pure scalar-in/scalar-out function citing the correlation
name and year. No external deps beyond numpy and math.
"""

from __future__ import annotations

import math

import numpy as np


# ============================================================================
# Oil PVT Correlations
# ============================================================================

def standing_rs_bubble(
    api: float,
    gas_grav: float,
    temp_f: float,
    p_res: float,
) -> tuple[float, float]:
    """
    Standing (1947) solution GOR and bubble point pressure.

    Ahmed, Reservoir Engineering Handbook, Ch. 4, Eq. 4.2.1 / 4.2.2.
    Rs = gas_grav * ((p/18.2 + 1.4) * 10**(0.0125*api - 0.00091*temp_f))**1.2048
    Pb = 18.2 * ((Rs/gas_grav)**0.83 * 10**(0.00091*temp_f - 0.0125*api) - 1.4)

    Args:
        api: Oil API gravity (>0)
        gas_grav: Gas specific gravity (air=1.0)
        temp_f: Reservoir temperature, degF
        p_res: Reservoir pressure, psia

    Returns:
        (Rs_scf_stb, Pb_psia) at reservoir conditions.
    """
    if p_res <= 0:
        return 0.0, 0.0

    # Standing Rs at reservoir pressure
    temp_term = 10 ** (0.0125 * api - 0.00091 * temp_f)
    rs = gas_grav * ((p_res / 18.2 + 1.4) * temp_term) ** 1.2048

    # Bubble point pressure from inverted correlation
    if rs <= 0:
        pb = 0.0
    else:
        inv_term = 10 ** (0.00091 * temp_f - 0.0125 * api)
        pb = 18.2 * ((rs / gas_grav) ** 0.83 * inv_term - 1.4)
        pb = max(pb, 0.0)

    return float(rs), float(pb)


def standing_bo(
    api: float,
    gas_grav: float,
    temp_f: float,
    rs: float,
) -> float:
    """
    Standing (1947) oil formation volume factor at bubble point.

    Ahmed, Ch. 4, Eq. 4.3.4.
    Bo = 0.9759 + 0.000120 * (rs * (gas_grav/oil_sg)^0.5 + 1.25*temp_f)^1.2
    where oil_sg = 141.5/(131.5+api)

    Args:
        api: Oil API gravity
        gas_grav: Gas specific gravity
        temp_f: Reservoir temperature, degF
        rs: Solution GOR at bubble point, scf/stb

    Returns:
        Bo, rb/stb
    """
    oil_sg = 141.5 / (131.5 + api)
    term = rs * math.sqrt(gas_grav / oil_sg) + 1.25 * temp_f
    bo = 0.9759 + 0.000120 * (term ** 1.2)
    return float(bo)


def vasquez_beggs_bo(
    api: float,
    gas_grav: float,
    temp_f: float,
    rs: float,
) -> float:
    """
    Vasquez-Beggs (1980) oil formation volume factor at bubble point.

    Ahmed, Ch. 4, Eq. 4.3.10 (Table 4.3 coefficients).
    Bo = 1.0 + C1*rs + (temp_f-60)*(api/gas_grav)*(C2 + C3*rs)

    API <= 30:  C1=4.677e-4, C2=1.751e-5, C3=-1.811e-8
    API > 30:   C1=4.670e-4, C2=1.100e-5, C3=1.337e-9

    Args:
        api: Oil API gravity
        gas_grav: Gas specific gravity
        temp_f: Reservoir temperature, degF
        rs: Solution GOR, scf/stb

    Returns:
        Bo, rb/stb
    """
    if api <= 30:
        c1, c2, c3 = 4.677e-4, 1.751e-5, -1.811e-8
    else:
        c1, c2, c3 = 4.670e-4, 1.100e-5, 1.337e-9

    bo = 1.0 + c1 * rs + (temp_f - 60.0) * (api / gas_grav) * (c2 + c3 * rs)
    return float(bo)


def almarhoun_bo(
    api: float,
    gas_grav: float,
    temp_f: float,
    rs: float,
    p: float,
) -> float:
    """
    Al-Marhoun (1988) saturated oil formation volume factor.

    Ahmed, Ch. 4, Eq. 4.3.12 (Table 4.4 coefficients).
    F = rs**0.74239 * gas_grav**0.323294 * oil_sg**-1.20204
    Bo = 0.497069 + 0.862963e-3*T_R + 0.182594e-2*F + 0.318099e-5*F**2
    where T_R = temp_f + 459.67 (Rankine)

    Note: This is the saturated Bo at bubble point. For p > Pb, use
    undersaturated correction externally.

    Args:
        api: Oil API gravity
        gas_grav: Gas specific gravity
        temp_f: Reservoir temperature, degF
        rs: Solution GOR at bubble point, scf/stb
        p: Pressure (at bubble point for saturated), psia

    Returns:
        Bo, rb/stb
    """
    oil_sg = 141.5 / (131.5 + api)
    t_r = temp_f + 459.67
    f = (rs ** 0.74239) * (gas_grav ** 0.323294) * (oil_sg ** -1.20204)
    bo = (
        0.497069
        + 0.862963e-3 * t_r
        + 0.182594e-2 * f
        + 0.318099e-5 * f * f
    )
    return float(bo)


# ============================================================================
# Oil Viscosity Correlations (Beggs-Robinson)
# ============================================================================

def beggs_robinson_muo_dead(
    api: float,
    temp_f: float,
) -> float:
    """
    Beggs-Robinson (1975) dead oil viscosity.

    Ahmed, Ch. 4, Eq. 4.4.1.
    x = 10**(3.0324 - 0.02023*api) * temp_f**-1.163
    mu_od = 10**x - 1

    Args:
        api: Oil API gravity
        temp_f: Temperature, degF

    Returns:
        Dead oil viscosity, cp
    """
    if temp_f <= 0:
        return 1.0
    x = (10 ** (3.0324 - 0.02023 * api)) * (temp_f ** -1.163)
    mu_od = (10 ** x) - 1.0
    return float(max(mu_od, 0.01))


def beggs_robinson_muo_live(
    mu_od: float,
    rs: float,
) -> float:
    """
    Beggs-Robinson live oil viscosity at bubble point.

    Ahmed, Ch. 4, Eq. 4.4.2.
    A = 10.715 * (rs + 100)**-0.515
    B = 5.44 * (rs + 150)**-0.338
    mu = A * mu_od**B

    Args:
        mu_od: Dead oil viscosity at reservoir temp, cp
        rs: Solution GOR at bubble point, scf/stb

    Returns:
        Live oil viscosity at bubble point, cp
    """
    if rs < 0:
        rs = 0.0
    a = 10.715 * ((rs + 100.0) ** -0.515)
    b = 5.44 * ((rs + 150.0) ** -0.338)
    mu = a * (mu_od ** b)
    return float(max(mu, 0.01))


# ============================================================================
# Gas PVT Correlations
# ============================================================================

def gas_z_papay(
    p_psia: float,
    temp_f: float,
    gas_grav: float,
) -> float:
    """
    Papay (1982) Z-factor correlation (simplified Standing-Katz).

    Ahmed, Ch. 3, Eq. 3.4.13 (Papay).
    z = 1 - 3.53*Ppr/(10**(0.9813*Tpr)) + 0.274*Ppr**2/(10**(0.8157*Tpr))

    Pseudocriticals (Standing):
    Tpc = 168 + 325*gas_grav - 12.5*gas_grav**2  (degR)
    Ppc = 677 + 15*gas_grav - 37.5*gas_grav**2   (psia)

    Args:
        p_psia: Pressure, psia
        temp_f: Temperature, degF
        gas_grav: Gas specific gravity (air=1.0)

    Returns:
        Z-factor (dimensionless)
    """
    t_pc = 168.0 + 325.0 * gas_grav - 12.5 * gas_grav * gas_grav
    p_pc = 677.0 + 15.0 * gas_grav - 37.5 * gas_grav * gas_grav

    t_r = (temp_f + 459.67) / t_pc
    p_r = p_psia / p_pc

    if t_r <= 0:
        return 1.0

    term1 = 3.53 * p_r / (10 ** (0.9813 * t_r))
    term2 = 0.274 * p_r * p_r / (10 ** (0.8157 * t_r))
    z = 1.0 - term1 + term2
    return float(max(z, 0.2))


def gas_bg(
    p_psia: float,
    temp_f: float,
    gas_grav: float,
) -> float:
    """
    Gas formation volume factor (real gas law).

    Bg [rb/Mscf] = 5.035 * z * T_R / p_psia
    where T_R = temp_f + 459.67 (Rankine)

    At standard conditions (14.7 psia, 60F, z=1): Bg = 5.035 * 519.67 / 14.7 = 178.0 rb/Mscf
    SPE1 reference: ~166.667 rb/Mscf at 14.7 psia (z~0.93 at 60F).

    Args:
        p_psia: Pressure, psia
        temp_f: Temperature, degF
        gas_grav: Gas specific gravity

    Returns:
        Bg, rb/Mscf
    """
    z = gas_z_papay(p_psia, temp_f, gas_grav)
    t_r = temp_f + 459.67
    if p_psia <= 0:
        return 0.0
    bg = 5.035 * z * t_r / p_psia
    return float(bg)


def lee_gonzalez_mug(
    p_psia: float,
    temp_f: float,
    gas_grav: float,
) -> float:
    """
    Lee-Gonzalez-Eakin (1966) gas viscosity.

    Ahmed, Ch. 3, Eq. 3.5.1.
    Mg = 28.9625 * gas_grav
    T_R = temp_f + 459.67
    z = gas_z_papay(p_psia, temp_f, gas_grav)
    rho_g = p * Mg / (z * 10.732 * T_R)   [lb/ft3]
    rho_gcc = rho_g / 62.428               [g/cc]
    K = (9.4 + 0.02*Mg) * T_R**1.5 / (209 + 19*Mg + T_R)
    X = 3.5 + 986/T_R + 0.01*Mg
    Y = 2.4 - 0.2*X
    mu = 1e-4 * K * exp(X * rho_gcc**Y)    [cp]

    Args:
        p_psia: Pressure, psia
        temp_f: Temperature, degF
        gas_grav: Gas specific gravity

    Returns:
        Gas viscosity, cp
    """
    mg = 28.9625 * gas_grav
    t_r = temp_f + 459.67
    z = gas_z_papay(p_psia, temp_f, gas_grav)

    if z <= 0 or t_r <= 0:
        return 0.02

    rho_g = p_psia * mg / (z * 10.732 * t_r)  # lb/ft3
    rho_gcc = rho_g / 62.428  # g/cc

    k = (9.4 + 0.02 * mg) * (t_r ** 1.5) / (209.0 + 19.0 * mg + t_r)
    x = 3.5 + 986.0 / t_r + 0.01 * mg
    y = 2.4 - 0.2 * x
    mu = 1e-4 * k * math.exp(x * (rho_gcc ** y))
    return float(max(mu, 0.005))


# ============================================================================
# Water PVT Correlations (McCain)
# ============================================================================

def mccain_bw(
    p_psia: float,
    temp_f: float,
) -> float:
    """
    McCain (1991) water formation volume factor.

    Ahmed, Ch. 3, Eq. 3.3.5.
    dVwT = -1.0001e-2 + 1.33391e-4*T + 5.50654e-7*T**2
    dVwp = -1.95301e-9*p*T - 1.72834e-13*p**2*T - 3.58922e-7*p - 2.25341e-10*p**2
    Bw = (1 + dVwT) * (1 + dVwp)

    Args:
        p_psia: Pressure, psia
        temp_f: Temperature, degF

    Returns:
        Bw, rb/stb
    """
    t = temp_f
    p = p_psia
    dvwt = -1.0001e-2 + 1.33391e-4 * t + 5.50654e-7 * t * t
    dvwp = (
        -1.95301e-9 * p * t
        - 1.72834e-13 * p * p * t
        - 3.58922e-7 * p
        - 2.25341e-10 * p * p
    )
    bw = (1.0 + dvwt) * (1.0 + dvwp)
    return float(max(bw, 0.95))


def mccain_muw(
    temp_f: float,
    salinity_ppm: float,
) -> float:
    """
    McCain (1991) water viscosity.

    Ahmed, Ch. 3, Eq. 3.3.7 (approx).
    S = salinity_ppm / 10000 (weight fraction)
    A = 109.574 - 8.40564*S + 0.313314*S**2 + 8.72213e-3*S**3
    B = -1.12166 + 2.63951e-2*S - 6.79461e-4*S**2 - 5.47119e-5*S**3 + 1.55586e-6*S**4
    muw = A * temp_f**B   [cp at 14.7 psia]
    (pressure correction on water viscosity is small, omitted)

    Args:
        temp_f: Temperature, degF
        salinity_ppm: Salinity, ppm NaCl equiv

    Returns:
        Water viscosity, cp
    """
    s = salinity_ppm / 10000.0
    a = 109.574 - 8.40564 * s + 0.313314 * s * s + 8.72213e-3 * s * s * s
    b = (
        -1.12166
        + 2.63951e-2 * s
        - 6.79461e-4 * s * s
        - 5.47119e-5 * s * s * s
        + 1.55586e-6 * s * s * s * s
    )
    if temp_f <= 0:
        return 1.0
    muw = a * (temp_f ** b)
    return float(max(muw, 0.1))


# ============================================================================
# Relative Permeability Correlations
# ============================================================================

def _normalize_saturation(
    s: float,
    s_min: float,
    s_max: float,
) -> float:
    """Normalize saturation to [0, 1] range."""
    if s_max <= s_min:
        return 0.0
    s_n = (s - s_min) / (s_max - s_min)
    return float(max(0.0, min(1.0, s_n)))


def corey_swof(
    sw: float,
    swc: float,
    sorw: float,
    krw_max: float,
    kro_max: float,
    nw: float,
    no: float,
) -> tuple[float, float]:
    """
    Corey (1954) water-oil relative permeability.

    krw = krw_max * ((Sw - Swc) / (1 - Swc - Sorw))^nw
    kro = kro_max * ((1 - Sw - Sorw) / (1 - Swc - Sorw))^no

    Args:
        sw: Water saturation
        swc: Connate water saturation
        sorw: Residual oil saturation to water
        krw_max: Max water relperm at Sorw
        kro_max: Max oil relperm at Swc
        nw: Water Corey exponent
        no: Oil Corey exponent

    Returns:
        (krw, kro)
    """
    s_max = 1.0 - sorw
    if sw <= swc:
        return 0.0, kro_max
    if sw >= s_max:
        return krw_max, 0.0

    s_wn = _normalize_saturation(sw, swc, s_max)
    s_on = _normalize_saturation(1.0 - sw, 0.0, 1.0 - swc - sorw)

    krw = krw_max * (s_wn ** nw)
    kro = kro_max * (s_on ** no)

    return float(krw), float(kro)


def corey_sgof(
    sg: float,
    sgc: float,
    sorg: float,
    swc: float,
    krg_max: float,
    kro_max: float,
    ng: float,
    nog: float,
) -> tuple[float, float]:
    """
    Corey (1954) gas-oil relative permeability.

    krg = krg_max * ((Sg - Sgc) / (1 - Swc - Sgc - Sorg))^ng
    kro = kro_max * ((1 - Swc - Sg - Sorg) / (1 - Swc - Sgc - Sorg))^nog

    Args:
        sg: Gas saturation
        sgc: Critical gas saturation
        sorg: Residual oil saturation to gas
        swc: Connate water saturation
        krg_max: Max gas relperm
        kro_max: Max oil relperm
        ng: Gas Corey exponent
        nog: Oil-to-gas Corey exponent

    Returns:
        (krg, kro)
    """
    s_max = 1.0 - swc - sorg
    if sg <= sgc:
        return 0.0, kro_max
    if sg >= s_max:
        return krg_max, 0.0

    s_gn = _normalize_saturation(sg, sgc, s_max)
    s_on = _normalize_saturation(1.0 - swc - sg, 0.0, 1.0 - swc - sgc - sorg)

    krg = krg_max * (s_gn ** ng)
    kro = kro_max * (s_on ** nog)

    return float(krg), float(kro)


def let_swof(
    sw: float,
    swc: float,
    sorw: float,
    krw_max: float,
    kro_max: float,
    l_w: float,
    e_w: float,
    t_w: float,
    l_o: float,
    e_o: float,
    t_o: float,
) -> tuple[float, float]:
    """
    LET (Lomeland et al. 2005) water-oil relative permeability.

    kr = kr_max * (S**L) / (S**L + E * (1-S)**T)
    where S is normalized saturation.

    Args:
        sw: Water saturation
        swc: Connate water saturation
        sorw: Residual oil saturation to water
        krw_max: Max water relperm
        kro_max: Max oil relperm
        l_w, e_w, t_w: Water LET parameters
        l_o, e_o, t_o: Oil LET parameters

    Returns:
        (krw, kro)
    """
    s_max = 1.0 - sorw
    if sw <= swc:
        return 0.0, kro_max
    if sw >= s_max:
        return krw_max, 0.0

    s_wn = _normalize_saturation(sw, swc, s_max)
    s_on = 1.0 - s_wn

    krw = krw_max * (s_wn ** l_w) / (s_wn ** l_w + e_w * (s_on ** t_w))
    kro = kro_max * (s_on ** l_o) / (s_on ** l_o + e_o * (s_wn ** t_o))

    return float(krw), float(kro)


def let_sgof(
    sg: float,
    sgc: float,
    sorg: float,
    swc: float,
    krg_max: float,
    kro_max: float,
    l_g: float,
    e_g: float,
    t_g: float,
    l_o: float,
    e_o: float,
    t_o: float,
) -> tuple[float, float]:
    """
    LET (Lomeland et al. 2005) gas-oil relative permeability.

    Args:
        sg: Gas saturation
        sgc: Critical gas saturation
        sorg: Residual oil saturation to gas
        swc: Connate water saturation
        krg_max: Max gas relperm
        kro_max: Max oil relperm
        l_g, e_g, t_g: Gas LET parameters
        l_o, e_o, t_o: Oil-to-gas LET parameters

    Returns:
        (krg, kro)
    """
    s_max = 1.0 - swc - sorg
    if sg <= sgc:
        return 0.0, kro_max
    if sg >= s_max:
        return krg_max, 0.0

    s_gn = _normalize_saturation(sg, sgc, s_max)
    s_on = 1.0 - s_gn

    krg = krg_max * (s_gn ** l_g) / (s_gn ** l_g + e_g * (s_on ** t_g))
    kro = kro_max * (s_on ** l_o) / (s_on ** l_o + e_o * (s_gn ** t_o))

    return float(krg), float(kro)