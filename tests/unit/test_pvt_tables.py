"""Unit tests for PVT table builders and validators."""

from __future__ import annotations

import pytest

from opm_ai.preprocess import (
    FluidDescriptor,
    PVTBlocks,
    build_pvt_blocks,
    recommend_correlation,
    validate_pvt_blocks,
)


class TestPVTBlocks:
    """Tests for build_pvt_blocks and related functions."""

    def _make_spe1_fluid(self) -> FluidDescriptor:
        """Create fluid descriptor matching SPE1 example from spec."""
        return FluidDescriptor(
            api_gravity=35.0,
            gas_specific_gravity=0.75,
            gor=800.0,
            reservoir_temp_f=200.0,
            salinity_ppm=50000.0,
            pressure_range_psi=(14.7, 5000.0),
            unit_system="FIELD",
        )

    def test_build_pvt_blocks_field_units(self):
        """Build PVT blocks with FIELD units - all 7 blocks present."""
        fluid = self._make_spe1_fluid()
        blocks = build_pvt_blocks(fluid)

        assert isinstance(blocks, PVTBlocks)
        assert "PVTO" in blocks.pvt_oil
        assert "PVDG" in blocks.pvdg
        assert "PVTW" in blocks.pvt_water
        assert "ROCK" in blocks.rock
        assert "DENSITY" in blocks.density
        assert "SWOF" in blocks.swof
        assert "SGOF" in blocks.sgof

        # Verify blocks end with /
        for block_name, block_str in [
            ("PVTO", blocks.pvt_oil),
            ("PVDG", blocks.pvdg),
            ("PVTW", blocks.pvt_water),
            ("ROCK", blocks.rock),
            ("DENSITY", blocks.density),
            ("SWOF", blocks.swof),
            ("SGOF", blocks.sgof),
        ]:
            lines = [l.strip() for l in block_str.strip().split("\n") if l.strip()]
            assert lines[0] == block_name, f"{block_name} should start with keyword"
            assert lines[-1] == "/", f"{block_name} should end with /"

    def test_build_pvt_blocks_metric_units(self):
        """Build PVT blocks with METRIC units."""
        fluid = FluidDescriptor(
            api_gravity=35.0,
            gas_specific_gravity=0.75,
            gor=800.0 * 0.17811,  # convert scf/stb to sm3/sm3
            reservoir_temp_c=93.33,
            salinity_ppm=50000.0,
            pressure_range_psi=(1.01325, 344.74),  # 14.7 psi, 5000 psi in bar
            unit_system="METRIC",
        )
        blocks = build_pvt_blocks(fluid)

        assert isinstance(blocks, PVTBlocks)
        for block_name, block_str in [
            ("PVTO", blocks.pvt_oil),
            ("PVDG", blocks.pvdg),
            ("PVTW", blocks.pvt_water),
            ("ROCK", blocks.rock),
            ("DENSITY", blocks.density),
            ("SWOF", blocks.swof),
            ("SGOF", blocks.sgof),
        ]:
            assert block_name in block_str
            lines = [l.strip() for l in block_str.strip().split("\n") if l.strip()]
            assert lines[0] == block_name
            assert lines[-1] == "/"

    def test_validate_pvt_blocks_field_clean(self):
        """Validation should pass for SPE1-like fluid with FIELD units."""
        fluid = self._make_spe1_fluid()
        blocks = build_pvt_blocks(fluid)
        errors = validate_pvt_blocks(blocks, "FIELD")
        assert errors == [], f"Validation errors: {errors}"

    def test_validate_pvt_blocks_metric_clean(self):
        """Validation should pass for METRIC units."""
        fluid = FluidDescriptor(
            api_gravity=35.0,
            gas_specific_gravity=0.75,
            gor=800.0 * 0.17811,
            reservoir_temp_c=93.33,
            salinity_ppm=50000.0,
            pressure_range_psi=(1.01325, 344.74),
            unit_system="METRIC",
        )
        blocks = build_pvt_blocks(fluid)
        errors = validate_pvt_blocks(blocks, "METRIC")
        assert errors == [], f"Validation errors: {errors}"


class TestRecommendCorrelation:
    """Tests for the correlation advisor (offline fallback)."""

    def test_offline_fallback_standing(self):
        """API > 30 and gas_grav < 0.8 -> Standing."""
        fluid = FluidDescriptor(
            api_gravity=35.0,
            gas_specific_gravity=0.75,
            gor=800.0,
            reservoir_temp_f=200.0,
            unit_system="FIELD",
        )
        corr, explanation = recommend_correlation(fluid, region=None)
        assert corr == "Standing"
        assert "offline fallback" in explanation.lower()
        assert "api>30" in explanation.lower() or "api > 30" in explanation.lower()

    def test_offline_fallback_vasquez_beggs(self):
        """API <= 30 -> VasquezBeggs."""
        fluid = FluidDescriptor(
            api_gravity=25.0,
            gas_specific_gravity=0.8,
            gor=500.0,
            reservoir_temp_f=180.0,
            unit_system="FIELD",
        )
        corr, explanation = recommend_correlation(fluid, region=None)
        assert corr == "VasquezBeggs"
        assert "offline fallback" in explanation.lower()
        assert "api<=30" in explanation.lower() or "api <= 30" in explanation.lower()

    def test_offline_fallback_almarhoun_middle_east(self):
        """Region middle_east or carbonate -> AlMarhoun."""
        fluid = FluidDescriptor(
            api_gravity=35.0,
            gas_specific_gravity=0.85,
            gor=800.0,
            reservoir_temp_f=220.0,
            unit_system="FIELD",
        )
        corr, explanation = recommend_correlation(fluid, region="middle_east")
        assert corr == "AlMarhoun"
        assert "offline fallback" in explanation.lower()
        assert "middle east" in explanation.lower() or "carbonate" in explanation.lower()

    def test_offline_fallback_almarhoun_carbonate(self):
        """Region carbonate -> AlMarhoun."""
        fluid = FluidDescriptor(
            api_gravity=35.0,
            gas_specific_gravity=0.85,
            gor=800.0,
            reservoir_temp_f=220.0,
            unit_system="FIELD",
        )
        corr, explanation = recommend_correlation(fluid, region="carbonate")
        assert corr == "AlMarhoun"
        assert "offline fallback" in explanation.lower()

    def test_recommend_correlation_never_raises(self):
        """recommend_correlation should never raise, even with bad inputs."""
        fluid = FluidDescriptor(
            api_gravity=35.0,
            gas_specific_gravity=0.75,
            gor=800.0,
            reservoir_temp_f=200.0,
            unit_system="FIELD",
        )
        # Should not raise even if LLM client is unavailable
        corr, explanation = recommend_correlation(fluid, region="unknown")
        assert corr in ("Standing", "VasquezBeggs", "AlMarhoun")
        assert isinstance(explanation, str)
        assert len(explanation) > 0


class TestPVTBlockFormatting:
    """Tests for specific formatting requirements in rendered blocks."""

    def _make_spe1_fluid(self) -> FluidDescriptor:
        return FluidDescriptor(
            api_gravity=35.0,
            gas_specific_gravity=0.75,
            gor=800.0,
            reservoir_temp_f=200.0,
            salinity_ppm=50000.0,
            pressure_range_psi=(14.7, 5000.0),
            unit_system="FIELD",
        )

    def test_pvto_format_groups_by_rs(self):
        """PVTO should group rows by RS value with RS header lines."""
        fluid = self._make_spe1_fluid()
        blocks = build_pvt_blocks(fluid)

        # PVTO format: RS header, then P BO MUO lines, then / per group, final /
        lines = blocks.pvt_oil.strip().split("\n")
        assert lines[0] == "PVTO"

        # Find RS header lines (single value) and data lines (3 values)
        rs_headers = []
        data_lines = []
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) == 1 and parts[0] != "/":
                rs_headers.append(float(parts[0]))
            elif len(parts) == 3:
                data_lines.append(parts)

        assert len(rs_headers) > 1, "Should have multiple RS groups"
        assert len(data_lines) > 0, "Should have data rows"

    def test_pvdg_pressure_increasing_bg_decreasing(self):
        """PVDG pressure strictly increasing, BG strictly decreasing."""
        fluid = self._make_spe1_fluid()
        blocks = build_pvt_blocks(fluid)

        lines = [l.strip() for l in blocks.pvdg.strip().split("\n") if l.strip()]
        data_lines = [l for l in lines if not l.startswith("PVDG") and l != "/"]

        prev_p = -1.0
        prev_bg = float("inf")
        for line in data_lines:
            p, bg, mug = map(float, line.split())
            assert p > prev_p, f"Pressure not increasing: {prev_p} -> {p}"
            assert bg < prev_bg, f"BG not decreasing: {prev_bg} -> {bg}"
            assert bg > 0, f"BG <= 0: {bg}"
            assert mug > 0, f"MUG <= 0: {mug}"
            prev_p = p
            prev_bg = bg

    def test_swof_sw_strictly_increasing(self):
        """SWOF water saturation strictly increasing."""
        fluid = self._make_spe1_fluid()
        blocks = build_pvt_blocks(fluid)

        lines = [l.strip() for l in blocks.swof.strip().split("\n") if l.strip()]
        data_lines = [l for l in lines if not l.startswith("SWOF") and l != "/"]

        prev_sw = -1.0
        for line in data_lines:
            sw, krw, kro, pcow = map(float, line.split())
            assert sw > prev_sw, f"Sw not increasing: {prev_sw} -> {sw}"
            assert 0.0 <= krw <= 1.0, f"KRW out of bounds: {krw}"
            assert 0.0 <= kro <= 1.0, f"KRO out of bounds: {kro}"
            prev_sw = sw

        # First row KRW == 0 at Swc
        first_sw, first_krw, first_kro, _ = map(float, data_lines[0].split())
        assert abs(first_krw) < 1e-6, f"First KRW should be 0: {first_krw}"

        # Last row KRO == 0 at Sw=1.0
        last_sw, last_krw, last_kro, _ = map(float, data_lines[-1].split())
        assert abs(last_sw - 1.0) < 1e-6, f"Last Sw should be 1.0: {last_sw}"
        assert abs(last_kro) < 1e-6, f"Last KRO should be 0: {last_kro}"

    def test_sgof_sg_strictly_increasing(self):
        """SGOF gas saturation strictly increasing."""
        fluid = self._make_spe1_fluid()
        blocks = build_pvt_blocks(fluid)

        lines = [l.strip() for l in blocks.sgof.strip().split("\n") if l.strip()]
        data_lines = [l for l in lines if not l.startswith("SGOF") and l != "/"]

        prev_sg = -1.0
        for line in data_lines:
            sg, krg, kro, pcog = map(float, line.split())
            assert sg > prev_sg, f"Sg not increasing: {prev_sg} -> {sg}"
            assert 0.0 <= krg <= 1.0, f"KRG out of bounds: {krg}"
            assert 0.0 <= kro <= 1.0, f"KRO out of bounds: {kro}"
            prev_sg = sg

        # First row: Sg=0, KRG=0, KRO=kro_max
        first_sg, first_krg, first_kro, _ = map(float, data_lines[0].split())
        assert abs(first_sg) < 1e-6, f"First Sg should be 0: {first_sg}"
        assert abs(first_krg) < 1e-6, f"First KRG should be 0: {first_krg}"
        assert first_kro > 0.9, f"First KRO should be ~1.0: {first_kro}"

    def test_density_three_positive_values(self):
        """DENSITY block should have three positive numbers."""
        fluid = self._make_spe1_fluid()
        blocks = build_pvt_blocks(fluid)

        lines = [l.strip() for l in blocks.density.strip().split("\n") if l.strip()]
        data_lines = [l for l in lines if not l.startswith("DENSITY") and l != "/"]
        assert len(data_lines) == 1
        oil, water, gas = map(float, data_lines[0].split())
        assert oil > 0, f"Oil density <= 0: {oil}"
        assert water > 0, f"Water density <= 0: {water}"
        assert gas > 0, f"Gas density <= 0: {gas}"

    def test_rock_single_row_with_compressibility(self):
        """ROCK should have single row with pressure and compressibility."""
        fluid = self._make_spe1_fluid()
        blocks = build_pvt_blocks(fluid)

        lines = [l.strip() for l in blocks.rock.strip().split("\n") if l.strip()]
        data_lines = [l for l in lines if not l.startswith("ROCK") and l != "/"]
        assert len(data_lines) == 1
        p, cr = map(float, data_lines[0].split())
        assert p > 0, f"Rock pressure <= 0: {p}"
        assert cr > 0, f"Rock compressibility <= 0: {cr}"

    def test_pvtw_single_row(self):
        """PVTW should have single row with P, BW, CW, MUW, VISCO."""
        fluid = self._make_spe1_fluid()
        blocks = build_pvt_blocks(fluid)

        lines = [l.strip() for l in blocks.pvt_water.strip().split("\n") if l.strip()]
        data_lines = [l for l in lines if not l.startswith("PVTW") and l != "/"]
        assert len(data_lines) == 1
        p, bw, cw, muw, visco = map(float, data_lines[0].split())
        assert p > 0
        assert bw > 0
        assert cw >= 0
        assert muw > 0
        assert visco >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])