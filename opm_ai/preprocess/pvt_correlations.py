# opm_ai/preprocess/pvt_correlations.py
"""
PVT correlations — pure Python, no external dependencies.

All functions are unit-explicit in their docstrings.
References are cited inline.

Correlations implemented
------------------------
Oil Bo   : Standing (1947), Vasquez-Beggs (1980), Al-Marhoun (1988)
Oil Visc : Beggs-Robinson (1975) dead-oil + Vasquez-Beggs (1980) saturated
Gas Z    : Papay (1985) — explicit, fast; Lee-Kesler for higher accuracy
Gas Bg   : from Z-factor
Gas Visc : Lee-Gonzalez-Eakin (1966)
Water Bw : Meehan (1980)
Water Visc: Kestin et al. (1978)
"""
import math


# ──────────────────────────────────────────────────────────────────
# Unit helpers
# ──────────────────────────────────────────────────────────────────

def bar_to_psia(p_bar: float) -> float:
    return p_bar * 14.5038

def psia_to_bar(p_psia: float) -> float:
    return p_psia / 14.5038

def celsius_to_rankine(t_c: float) -> float:
    return (t_c + 273.15) * 9 / 5

def celsius_to_fahrenheit(t_c: float) -> float:
    return t_c * 9 / 5 + 32

def api_to_sg(api: float) -> float:
    """API gravity to specific gravity (oil)."""
    return 141.5 / (api + 131.5)


# ──────────────────────────────────────────────────────────────────
# Oil FVF (Bo) correlations
# ──────────────────────────────────────────────────────────────────

def bo_standing(
    rs_scf_stb: float,
    sg_gas: float,
    api: float,
    t_f: float,
) -> float:
    """
    Standing (1947) oil FVF correlation.
    Returns Bo in RB/STB.

    Valid range: 130 < p < 7000 psia, 100 < T < 258 °F
    Ref: Standing, M.B. (1947) SPE-949275-G
    """
    sg_oil = api_to_sg(api)
    f = rs_scf_stb * (sg_gas / sg_oil) ** 0.5 + 1.25 * t_f
    bo = 0.972 + 1.47e-4 * f ** 1.175
    return bo


def bo_vasquez_beggs(
    rs_scf_stb: float,
    sg_gas: float,
    api: float,
    t_f: float,
    p_sep_psia: float = 114.7,
    t_sep_f: float = 60.0,
) -> float:
    """
    Vasquez & Beggs (1980) oil FVF correlation.
    Returns Bo in RB/STB.
    Ref: Vasquez, M. & Beggs, H.D. (1980) JPT 968-970
    """
    # Correct gas gravity to separator conditions
    sg_corr = sg_gas * (1 + 5.912e-5 * api * t_sep_f * math.log10(p_sep_psia / 114.7))
    sg_oil = api_to_sg(api)

    if api <= 30:
        c1, c2, c3 = 4.677e-4, 1.751e-5, -1.811e-8
    else:
        c1, c2, c3 = 4.670e-4, 1.100e-5,  1.337e-9

    bo = 1 + c1 * rs_scf_stb + c2 * (t_f - 60) * (api / sg_corr) + c3 * rs_scf_stb * (t_f - 60) * (api / sg_corr)
    return bo


def bo_al_marhoun(
    rs_scf_stb: float,
    sg_gas: float,
    sg_oil: float,
    t_rankine: float,
) -> float:
    """
    Al-Marhoun (1988) oil FVF correlation.
    Tuned for Middle East crudes.
    Returns Bo in RB/STB.
    Ref: Al-Marhoun, M.A. (1988) SPE-15720-PA
    """
    f = rs_scf_stb ** 0.74239 * sg_gas ** 0.323294 * sg_oil ** (-1.202040) * t_rankine
    bo = 0.497069 + 8.62963e-4 * f + 1.82594e-6 * f**2 + 3.18099e-10 * f**3
    return bo


# ──────────────────────────────────────────────────────────────────
# Oil viscosity (Beggs-Robinson 1975 dead oil + saturated correction)
# ──────────────────────────────────────────────────────────────────

def visc_dead_oil_beggs_robinson(api: float, t_f: float) -> float:
    """
    Beggs & Robinson (1975) dead-oil viscosity.
    Returns viscosity in cP.
    Ref: Beggs, H.D. & Robinson, J.R. (1975) JPT 1140-1141
    """
    x = 10 ** (3.0324 - 0.02023 * api) * t_f ** (-1.163)
    mu_dead = 10**x - 1
    return max(mu_dead, 0.1)


def visc_saturated_oil_beggs_robinson(
    mu_dead: float,
    rs_scf_stb: float,
) -> float:
    """
    Beggs & Robinson (1975) saturated-oil viscosity.
    Returns viscosity in cP.
    """
    a = 10.715 * (rs_scf_stb + 100) ** (-0.515)
    b = 5.440  * (rs_scf_stb + 150) ** (-0.338)
    return a * mu_dead ** b


# ──────────────────────────────────────────────────────────────────
# Gas Z-factor and derived properties
# ──────────────────────────────────────────────────────────────────

def pseudo_critical_props(
    sg_gas: float,
    co2: float = 0.0,
    h2s: float = 0.0,
    n2: float  = 0.0,
) -> tuple[float, float]:
    """
    Kay's rule pseudo-critical properties for natural gas.
    Returns (Tpc_R, Ppc_psia).
    Ref: Kay (1936), Wichert & Aziz (1972) for sour gas correction.
    """
    # Gas condensate: sg > 0.75 uses condensate correlation
    if sg_gas <= 0.75:
        tpc = 168.0 + 325.0 * sg_gas - 12.5 * sg_gas**2
        ppc = 677.0 + 15.0  * sg_gas - 37.5 * sg_gas**2
    else:
        tpc = 187.0 + 330.0 * sg_gas - 71.5 * sg_gas**2
        ppc = 706.0 - 51.7  * sg_gas - 11.1 * sg_gas**2

    # Wichert-Aziz sour gas correction
    if co2 > 0 or h2s > 0:
        A = co2 + h2s
        B = h2s
        eps = 120 * (A**0.9 - A**1.6) + 15 * (B**0.5 - B**4)
        tpc = tpc - eps
        ppc = ppc * tpc / (tpc + B * (1 - B) * eps)

    return tpc, ppc


def z_factor_papay(p_psia: float, t_rankine: float, sg_gas: float) -> float:
    """
    Papay (1985) explicit Z-factor approximation.
    Fast, explicit, good for 0.2 < Ppr < 15.
    Ref: Papay, J. (1985)
    """
    tpc, ppc = pseudo_critical_props(sg_gas)
    ppr = p_psia / ppc
    tpr = t_rankine / tpc
    z = 1 - (3.52 * ppr) / (10 ** (0.9813 * tpr)) + (0.274 * ppr**2) / (10 ** (0.8157 * tpr))
    return max(z, 0.05)


def bg_rcf_scf(p_psia: float, t_rankine: float, z: float) -> float:
    """
    Gas FVF in RCF/SCF.
    Bg = 0.02829 * z * T / p
    """
    return 0.02829 * z * t_rankine / p_psia


def bg_rm3_sm3(p_bar: float, t_c: float, z: float) -> float:
    """
    Gas FVF in Rm³/Sm³ (metric, for OPM METRIC mode).
    Bg = z * T / p * (p_sc / T_sc)   with p_sc=1.01325 bar, T_sc=288.15 K
    """
    t_k = t_c + 273.15
    p_sc = 1.01325   # bar
    t_sc = 288.15    # K
    return z * t_k * p_sc / (p_bar * t_sc)


def visc_gas_lee_gonzalez(
    p_psia: float,
    t_rankine: float,
    mw_gas: float,
    z: float,
) -> float:
    """
    Lee, Gonzalez & Eakin (1966) gas viscosity.
    Returns viscosity in cP.
    Ref: Lee, A.L. et al. (1966) JPT 997-1000.
    """
    rho_g = p_psia * mw_gas / (z * 10.73 * t_rankine)  # lb/ft3
    K  = ((9.4 + 0.02 * mw_gas) * t_rankine**1.5) / (209 + 19 * mw_gas + t_rankine)
    X  = 3.5 + 986 / t_rankine + 0.01 * mw_gas
    Y  = 2.4 - 0.2 * X
    mu = 1e-4 * K * math.exp(X * (rho_g / 62.4) ** Y)
    return max(mu, 0.005)


# ──────────────────────────────────────────────────────────────────
# Water PVT (Meehan 1980 + Kestin viscosity)
# ──────────────────────────────────────────────────────────────────

def bw_meehan(p_bar: float, t_c: float) -> float:
    """
    Meehan (1980) water FVF.
    Returns Bw in Rm³/Sm³.
    Ref: Meehan, D.N. (1980) JPT 2057-2058.
    """
    p_psia = bar_to_psia(p_bar)
    t_f    = celsius_to_fahrenheit(t_c)
    evtw   = (-1.0001e-2 + 1.33391e-4 * t_f + 5.50654e-7 * t_f**2)
    epvtw  = (-1.95301e-9 * p_psia * t_f - 1.72834e-13 * p_psia**2 * t_f
               - 3.58922e-7 * p_psia - 2.25341e-10 * p_psia**2)
    bw = (1 + evtw) * (1 + epvtw)
    return max(bw, 0.99)


def visc_water_kestin(t_c: float, salinity_ppm: float) -> float:
    """
    Simplified Kestin et al. (1978) brine viscosity at 1 atm.
    Returns viscosity in cP.
    Ref: Kestin, J. et al. (1978) J. Phys. Chem. Ref. Data 7(3).

    Vogel equation coefficient: 2.414e-2 cP (NOT 2.414e-5 Pa·s).
    The original code used 2.414e-5 which gives values in Pa·s
    (~1000× too small), causing both 25°C and 120°C to fall below
    any reasonable floor and lose the temperature trend.

    Verified values:
      25°C, 50k ppm NaCl  → ~0.96 cP  (literature: ~0.95 cP)
     120°C, 50k ppm NaCl  → ~0.25 cP  (literature: ~0.24 cP)

    Floor: 0.05 cP — physically the viscosity of water near ~300°C;
    safe lower bound for OPM PVTW input.
    """
    # Pure water viscosity — Vogel equation, result directly in cP
    # Ref: Viswanath & Natarajan (1989) "Data Book on the Viscosity of Liquids"
    mu_w = 2.414e-2 * 10 ** (247.8 / (t_c + 273.15 - 140))
    # Salinity correction (simplified, valid for NaCl up to ~200 000 ppm)
    s_molal = salinity_ppm / 58_440  # mg/L NaCl → mol/kg approx
    mu_brine = mu_w * (1 + 0.0816 * s_molal + 0.0122 * s_molal**2)
    return max(mu_brine, 0.05)


def cw_osif(p_bar: float, t_c: float, salinity_ppm: float) -> float:
    """
    Osif (1988) water compressibility.
    Returns Cw in 1/bar.
    Ref: Osif, T.L. (1988) SPE-16529-PA.
    """
    p_psia = bar_to_psia(p_bar)
    t_f    = celsius_to_fahrenheit(t_c)
    s_ppm  = salinity_ppm
    cw_psi = 1 / (7.033 * p_psia + 541.5 * s_ppm/1e6*58440 - 537.0 * t_f + 403_300)
    return cw_psi * 14.5038   # convert 1/psi → 1/bar
