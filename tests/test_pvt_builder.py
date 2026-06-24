# tests/test_pvt_builder.py
"""
Tests for pvt_builder.build_pvt_props — the Stage-2 PVT computation layer.
All tests are offline (no LLM, no OPM binary).
"""
import pytest
from opm_ai.preprocess.pvt_builder import build_pvt_props, PVTProps


# ---- Water tests -----------------------------------------------------------

class TestWaterPVT:
    def test_pvtw_fields_present(self):
        pvt = build_pvt_props(350.0, 80.0, "oil_water")
        assert pvt.pvtw_p_ref == 350.0
        assert pvt.pvtw_bw   >  0
        assert pvt.pvtw_cw   >  0
        assert pvt.pvtw_visc >  0

    def test_water_visc_decreases_with_temperature(self):
        pvt_cold = build_pvt_props(350.0, 25.0,  "oil_water", salinity_ppm=50_000)
        pvt_hot  = build_pvt_props(350.0, 120.0, "oil_water", salinity_ppm=50_000)
        assert pvt_cold.pvtw_visc > pvt_hot.pvtw_visc, (
            f"Cold brine ({pvt_cold.pvtw_visc:.4f} cP) should be "
            f"more viscous than hot ({pvt_hot.pvtw_visc:.4f} cP)"
        )

    def test_water_fvf_close_to_unity(self):
        pvt = build_pvt_props(200.0, 60.0, "oil_water")
        assert 0.99 <= pvt.pvtw_bw <= 1.10

    def test_compressibility_positive_and_small(self):
        pvt = build_pvt_props(350.0, 80.0, "oil_water")
        assert 1e-7 < pvt.pvtw_cw < 1e-3


# ---- Oil_water fluid system ------------------------------------------------

class TestOilWater:
    def test_pvcdo_fields_set(self):
        pvt = build_pvt_props(350.0, 80.0, "oil_water")
        assert pvt.pvcdo_bo   is not None
        assert pvt.pvcdo_visc is not None
        assert pvt.pvto_rows  == []
        assert pvt.pvdg_rows  == []

    def test_dead_oil_bo_realistic(self):
        pvt = build_pvt_props(200.0, 70.0, "oil_water", api=35.0)
        assert 1.0 <= pvt.pvcdo_bo <= 1.5

    def test_dead_oil_visc_reasonable(self):
        pvt = build_pvt_props(200.0, 70.0, "oil_water", api=35.0)
        assert 0.1 <= pvt.pvcdo_visc <= 50.0

    def test_light_oil_lower_visc_than_heavy(self):
        pvt_light = build_pvt_props(300.0, 80.0, "oil_water", api=45.0)
        pvt_heavy = build_pvt_props(300.0, 80.0, "oil_water", api=15.0)
        assert pvt_light.pvcdo_visc < pvt_heavy.pvcdo_visc


# ---- Black oil fluid system ------------------------------------------------

class TestBlackOil:
    def test_pvto_and_pvdg_populated(self):
        pvt = build_pvt_props(350.0, 80.0, "black_oil")
        assert len(pvt.pvto_rows) > 0
        assert len(pvt.pvdg_rows) > 0

    def test_pvto_pressures_ascending(self):
        pvt = build_pvt_props(350.0, 80.0, "black_oil")
        pressures = [row[1][0][0] for row in pvt.pvto_rows]
        assert pressures == sorted(pressures)

    def test_pvdg_pressures_ascending(self):
        pvt = build_pvt_props(350.0, 80.0, "black_oil")
        pressures = [row[0] for row in pvt.pvdg_rows]
        assert pressures == sorted(pressures)

    def test_pvdg_bg_decreases_with_pressure(self):
        """Bg must decrease as pressure increases (gas compresses)."""
        pvt = build_pvt_props(350.0, 80.0, "black_oil")
        bgs = [row[1] for row in pvt.pvdg_rows]
        assert bgs == sorted(bgs, reverse=True)

    def test_pvdg_visc_positive(self):
        pvt = build_pvt_props(350.0, 80.0, "black_oil")
        for _, _, visc in pvt.pvdg_rows:
            assert visc > 0

    def test_n_pvt_points_respected(self):
        pvt = build_pvt_props(350.0, 80.0, "black_oil", n_pvt_points=5)
        assert len(pvt.pvdg_rows) == 5
        assert len(pvt.pvto_rows) == 5


# ---- Gas_water fluid system ------------------------------------------------

class TestGasWater:
    def test_pvdg_populated_no_oil(self):
        pvt = build_pvt_props(250.0, 90.0, "gas_water")
        assert len(pvt.pvdg_rows) > 0
        assert pvt.pvcdo_bo is None
        assert pvt.pvto_rows == []

    def test_gas_density_from_sg(self):
        pvt = build_pvt_props(250.0, 90.0, "gas_water", sg_gas=0.65)
        assert pvt.rho_gas == pytest.approx(0.65 * 1.225, rel=1e-3)


# ---- Dry gas ---------------------------------------------------------------

class TestDryGas:
    def test_dry_gas_pvdg_only(self):
        pvt = build_pvt_props(300.0, 100.0, "dry_gas")
        assert len(pvt.pvdg_rows) > 0
        assert pvt.pvcdo_bo is None


# ---- Integration: builder wires PVT into ReservoirDescription --------------

class TestBuilderIntegration:
    def test_build_from_description_populates_pvt(self):
        from opm_ai.builder.models import ReservoirDescription, FluidSystem
        from opm_ai.builder.builder import build_from_description

        rd = ReservoirDescription(
            fluid_system=FluidSystem.OIL_WATER,
            p_init=250.0,
            t_res=75.0,
            salinity_ppm=30_000,
        )
        result = build_from_description(rd)
        # PVT fields must be overwritten from defaults
        assert result.description.water_visc != 0.5   # default was 0.5
        assert result.description.water_fvf  != 1.0   # default was 1.0
        assert result.description.oil_fvf    >  1.0   # expansion from reservoir T

    def test_deck_contains_pvtw_keyword(self):
        from opm_ai.builder.models import ReservoirDescription, FluidSystem
        from opm_ai.builder.builder import build_from_description

        rd = ReservoirDescription(fluid_system=FluidSystem.OIL_WATER)
        result = build_from_description(rd)
        assert "PVTW" in result.deck_text
        assert "PVCDO" in result.deck_text

    def test_black_oil_deck_has_pvto_pvdg(self):
        from opm_ai.builder.models import ReservoirDescription, FluidSystem
        from opm_ai.builder.builder import build_from_description

        rd = ReservoirDescription(fluid_system=FluidSystem.BLACK_OIL)
        result = build_from_description(rd)
        assert "PVTO" in result.deck_text
        assert "PVDG" in result.deck_text

    def test_gas_water_deck_has_pvdg_no_pvto(self):
        from opm_ai.builder.models import ReservoirDescription, FluidSystem
        from opm_ai.builder.builder import build_from_description

        rd = ReservoirDescription(fluid_system=FluidSystem.GAS_WATER)
        result = build_from_description(rd)
        assert "PVDG" in result.deck_text
        assert "PVTO" not in result.deck_text

    def test_density_block_uses_computed_values(self):
        """DENSITY line must not hardcode 800 / 1025 / 1.0 — must come from PVT."""
        from opm_ai.builder.models import ReservoirDescription, FluidSystem
        from opm_ai.builder.builder import build_from_description

        rd = ReservoirDescription(fluid_system=FluidSystem.OIL_WATER, api=40.0)
        result = build_from_description(rd)
        # 40 API oil SG ~0.825 → density ~825 kg/m3, not the old hardcoded 800
        assert "825" in result.deck_text or "824" in result.deck_text
