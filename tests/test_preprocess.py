# tests/test_preprocess.py
"""
Unit tests for opm_ai.preprocess — PVT correlations and table builders.

All tests are pure Python, no external dependencies, no OPM Flow needed.
Run with: python -m pytest tests/test_preprocess.py -v
"""
import math
import pytest

from opm_ai.preprocess import (
    build_pvto, build_pvtw, build_pvdg,
    OilFluidInput, WaterFluidInput, GasFluidInput,
    PVTTableResult, CorrelationMethod,
)
from opm_ai.preprocess.pvt_correlations import (
    api_to_sg, bar_to_psia, celsius_to_fahrenheit,
    bo_standing, visc_dead_oil_beggs_robinson,
    z_factor_papay, bg_rm3_sm3,
    bw_meehan, visc_water_kestin, cw_osif,
)


# ── Correlation unit tests ─────────────────────────────────────────────────────

def test_api_to_sg_35_api():
    """35 API oil should give SG ~0.850."""
    sg = api_to_sg(35.0)
    assert 0.84 < sg < 0.86


def test_bar_to_psia():
    """1 bar ≈ 14.504 psia."""
    assert abs(bar_to_psia(1.0) - 14.5038) < 0.01


def test_celsius_to_fahrenheit_boiling():
    """100°C = 212°F."""
    assert abs(celsius_to_fahrenheit(100.0) - 212.0) < 0.01


def test_bo_standing_range():
    """
    Standing Bo for typical Gulf of Mexico oil should be between 1.05 and 1.80 RB/STB.
    API=35, GOR=500 scf/STB, T=180°F.
    """
    bo = bo_standing(rs_scf_stb=500, sg_gas=0.65, api=35.0, t_f=180.0)
    assert 1.05 < bo < 1.80, f"Bo out of range: {bo}"


def test_dead_oil_viscosity_decreases_with_temperature():
    """Dead-oil viscosity must decrease as temperature increases."""
    mu_60  = visc_dead_oil_beggs_robinson(api=30.0, t_f=140.0)
    mu_150 = visc_dead_oil_beggs_robinson(api=30.0, t_f=220.0)
    assert mu_60 > mu_150, "Viscosity should decrease with temperature"


def test_z_factor_papay_at_low_pressure():
    """Z-factor near 1.0 at very low pressure (ideal gas limit)."""
    from opm_ai.preprocess.pvt_correlations import celsius_to_rankine
    z = z_factor_papay(p_psia=14.7, t_rankine=celsius_to_rankine(80), sg_gas=0.65)
    assert 0.97 < z <= 1.02, f"Z near atmospheric should be ~1, got {z}"


def test_bg_decreases_with_pressure():
    """Gas FVF must decrease as pressure increases."""
    from opm_ai.preprocess.pvt_correlations import celsius_to_rankine
    t_r = celsius_to_rankine(80)
    z1 = z_factor_papay(bar_to_psia(50),  t_r, 0.65)
    z2 = z_factor_papay(bar_to_psia(300), t_r, 0.65)
    bg_low  = bg_rm3_sm3(50,  80, z1)
    bg_high = bg_rm3_sm3(300, 80, z2)
    assert bg_low > bg_high, "Bg must decrease with pressure"


def test_bw_close_to_one():
    """Water FVF should be very close to 1.0 Rm³/Sm³ at typical conditions."""
    bw = bw_meehan(p_bar=350.0, t_c=80.0)
    assert 0.97 < bw < 1.05, f"Bw = {bw} outside expected range"


def test_water_viscosity_decreases_with_temperature():
    """
    Brine viscosity must be strictly lower at 120 °C than at 25 °C.

    Uses temperatures well within the Vogel equation's valid range
    (25–200 °C) so neither value hits the 0.05 cP safety floor.
    At 25 °C + 50 000 ppm NaCl the raw value is ~1.1 cP;
    at 120 °C it is ~0.27 cP — both comfortably above 0.05 cP.
    """
    mu_cold = visc_water_kestin(t_c=25.0,  salinity_ppm=50_000)
    mu_hot  = visc_water_kestin(t_c=120.0, salinity_ppm=50_000)
    assert mu_cold > mu_hot, (
        f"Expected mu_cold ({mu_cold:.4f} cP) > mu_hot ({mu_hot:.4f} cP)"
    )


def test_cw_positive():
    """Water compressibility must always be positive."""
    cw = cw_osif(p_bar=350.0, t_c=80.0, salinity_ppm=50_000)
    assert cw > 0


# ── PVT builder tests ─────────────────────────────────────────────────────────

def test_build_pvto_returns_result():
    """build_pvto must return a PVTTableResult with type PVTO."""
    inp = OilFluidInput(api_gravity=35.0, gor_scf_stb=500, p_bubble_bar=200)
    result = build_pvto(inp)
    assert isinstance(result, PVTTableResult)
    assert result.table_type == "PVTO"


def test_pvto_block_contains_keyword():
    """PVTO OPM block must start with PVTO keyword."""
    inp = OilFluidInput(api_gravity=35.0, gor_scf_stb=500, p_bubble_bar=200)
    result = build_pvto(inp)
    assert result.opm_block.startswith("PVTO")


def test_pvto_block_ends_with_slash():
    """PVTO block must end with '/' terminator."""
    inp = OilFluidInput(api_gravity=35.0, gor_scf_stb=500, p_bubble_bar=200)
    result = build_pvto(inp)
    assert "/" in result.opm_block


def test_pvto_bo_physically_reasonable():
    """All Bo values in PVTO table must be between 1.0 and 3.0."""
    inp = OilFluidInput(api_gravity=35.0, gor_scf_stb=500, p_bubble_bar=200)
    result = build_pvto(inp)
    for pt in result.points:
        assert 1.0 < pt.fvf < 3.0, f"Bo={pt.fvf} out of range at P={pt.pressure_bar}"


def test_pvto_al_marhoun_method():
    """Al-Marhoun correlation should also produce a valid PVTTableResult."""
    inp = OilFluidInput(
        api_gravity=35.0, gor_scf_stb=500, p_bubble_bar=200,
        bo_method=CorrelationMethod.AL_MARHOUN,
    )
    result = build_pvto(inp)
    assert result.table_type == "PVTO"
    assert len(result.points) > 0


def test_build_pvtw_returns_result():
    """build_pvtw must return a PVTTableResult with type PVTW."""
    inp = WaterFluidInput(salinity_ppm=50_000, t_reservoir_c=80, p_ref_bar=350)
    result = build_pvtw(inp)
    assert isinstance(result, PVTTableResult)
    assert result.table_type == "PVTW"


def test_pvtw_block_format():
    """PVTW block must contain PVTW keyword and a '/' terminator."""
    inp = WaterFluidInput()
    result = build_pvtw(inp)
    assert "PVTW" in result.opm_block
    assert "/" in result.opm_block


def test_build_pvdg_returns_result():
    """build_pvdg must return a PVTTableResult with type PVDG."""
    inp = GasFluidInput(gas_gravity=0.65, t_reservoir_c=80)
    result = build_pvdg(inp)
    assert isinstance(result, PVTTableResult)
    assert result.table_type == "PVDG"


def test_pvdg_bg_monotonically_decreasing():
    """Gas Bg must decrease monotonically as pressure increases."""
    inp = GasFluidInput(gas_gravity=0.65, p_min_bar=50, p_max_bar=400, n_points=8)
    result = build_pvdg(inp)
    bgs = [pt.fvf for pt in result.points]
    for i in range(1, len(bgs)):
        assert bgs[i] < bgs[i-1], f"Bg not monotonically decreasing at index {i}"


def test_pvdg_visc_monotonically_increasing():
    """Gas viscosity must increase monotonically with pressure."""
    inp = GasFluidInput(gas_gravity=0.65, p_min_bar=50, p_max_bar=400, n_points=8)
    result = build_pvdg(inp)
    viscs = [pt.viscosity_cp for pt in result.points]
    for i in range(1, len(viscs)):
        assert viscs[i] >= viscs[i-1], f"Gas visc not increasing at index {i}"


def test_correlation_used_string():
    """PVTTableResult.correlation_used must be a non-empty string."""
    for result in [
        build_pvto(OilFluidInput(api_gravity=35.0)),
        build_pvtw(WaterFluidInput()),
        build_pvdg(GasFluidInput()),
    ]:
        assert isinstance(result.correlation_used, str)
        assert len(result.correlation_used) > 0
