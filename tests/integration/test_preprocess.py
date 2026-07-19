"""Integration tests for preprocess module and builder fluid integration."""

import pytest
import tempfile
import subprocess
from pathlib import Path

from opm_ai.preprocess import FluidDescriptor, build_pvt_blocks, validate_pvt_blocks
from opm_ai.builder.builder import build_deck
from opm_ai.linter import LintResult


class TestPreprocessIntegration:
    """Integration tests for PVT block generation and builder integration."""

    def test_all_blocks_present(self):
        """Test that build_pvt_blocks generates all 7 PROPS blocks with keywords."""
        fluid = FluidDescriptor(
            api_gravity=35,
            gas_specific_gravity=0.75,
            gor=800,
            reservoir_temp_f=200,
            salinity_ppm=50000,
            pressure_range_psi=(14.7, 5000),
            unit_system="FIELD",
        )
        blocks = build_pvt_blocks(fluid)

        # Check all 7 blocks are present and contain their keywords
        assert "PVTW" in blocks.pvt_water
        assert "ROCK" in blocks.rock
        assert "SWOF" in blocks.swof
        assert "SGOF" in blocks.sgof
        assert "DENSITY" in blocks.density
        assert "PVDG" in blocks.pvdg
        assert "PVTO" in blocks.pvt_oil

        # Validate - should have no errors
        errors = validate_pvt_blocks(blocks, "FIELD")
        assert errors == [], f"Validation errors: {errors}"

    def test_builder_with_fluid(self):
        """Test build_deck with fluid descriptor produces fluid-specific tables."""
        fluid = FluidDescriptor(
            api_gravity=35,
            gas_specific_gravity=0.75,
            gor=800,
            reservoir_temp_f=200,
            salinity_ppm=50000,
            pressure_range_psi=(14.7, 5000),
            unit_system="FIELD",
        )

        desc = "10x10x3 grid, simple depletion, one producer"
        deck_text, lint_result = build_deck(desc, fluid=fluid)

        # Verify deck contains fluid-specific tables (not SPE1 hardcoded values)
        assert "PVTO" in deck_text
        # SPE1 hardcoded PVTO has 1.0620 at Rs=0.001 - our fluid tables should differ
        assert "1.0620" not in deck_text, "SPE1 hardcoded value should not appear with fluid"

        # Verify lint passes
        assert lint_result.passed
        assert len(lint_result.errors) == 0

    def test_builder_without_fluid_unchanged(self):
        """Test build_deck without fluid still produces SPE1 hardcoded tables."""
        desc = "10x10x3 grid, simple depletion, one producer"
        deck_text, lint_result = build_deck(desc)

        # Should contain SPE1 hardcoded value
        assert "1.0620" in deck_text, "SPE1 hardcoded value should appear without fluid"
        assert lint_result.passed
        assert len(lint_result.errors) == 0

    @pytest.mark.integration
    @pytest.mark.slow
    def test_flow_dry_run_with_fluid(self, tmp_path):
        """Test Flow dry-run validation with fluid-specific deck."""
        fluid = FluidDescriptor(
            api_gravity=35,
            gas_specific_gravity=0.75,
            gor=800,
            reservoir_temp_f=200,
            salinity_ppm=50000,
            pressure_range_psi=(14.7, 5000),
            unit_system="FIELD",
        )

        desc = "10x10x3 grid, simple depletion, one producer"
        deck_text, lint_result = build_deck(desc, fluid=fluid)

        assert lint_result.passed

        # Write deck to temp file
        deck_path = tmp_path / "FLUID_DECK.DATA"
        deck_path.write_text(deck_text)

        # Run Flow dry-run
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        result = subprocess.run(
            ["flow", "--enable-dry-run=true", f"--output-dir={output_dir}", str(deck_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, (
            f"Flow dry-run failed with exit code {result.returncode}.\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}\n"
            f"Deck (first 3000 chars):\n{deck_text[:3000]}"
        )

        # No errors in stderr
        assert "ERROR" not in result.stderr.upper(), f"Flow produced errors: {result.stderr}"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_flow_real_run_with_fluid(self, tmp_path):
        """Test full Flow simulation with fluid-specific deck (small grid, short schedule)."""
        fluid = FluidDescriptor(
            api_gravity=35,
            gas_specific_gravity=0.75,
            gor=800,
            reservoir_temp_f=200,
            salinity_ppm=50000,
            pressure_range_psi=(14.7, 5000),
            unit_system="FIELD",
        )

        # Use smaller grid and fewer timesteps for speed
        from opm_ai.builder.models import ModelSpec, ReservoirSpec, WellSpec, WellType, ScenarioType

        spec = ModelSpec(
            scenario=ScenarioType.DEPLETION,
            title="Fluid Test - Small Depletion",
            reservoir=ReservoirSpec(nx=5, ny=5, nz=3),
            wells=[
                WellSpec(
                    name="PROD1",
                    well_type=WellType.PROD,
                    i=5,
                    j=5,
                    k1=1,
                    k2=3,
                    control_mode="RATE",
                    target_rate=500.0,
                    bhp_limit=2000.0,
                )
            ],
            start_date="1 'JAN' 2015",
            timesteps=[30.0] * 3 + [90.0] * 2,  # 3 monthly + 2 quarterly = ~270 days
            field_units=True,
            fluid=fluid,
        )

        deck_text, lint_result = build_deck_from_spec(spec)
        assert lint_result.passed

        # Write deck
        deck_path = tmp_path / "SMALL_FLUID.DATA"
        deck_path.write_text(deck_text)

        # Run full Flow
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = subprocess.run(
            ["flow", f"--output-dir={output_dir}", str(deck_path)],
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert result.returncode == 0, (
            f"Flow simulation failed with exit code {result.returncode}.\n"
            f"STDOUT: {result.stdout[-2000:] if result.stdout else 'empty'}\n"
            f"STDERR: {result.stderr[-2000:] if result.stderr else 'empty'}"
        )

        # Check for output files
        smspec_files = list(output_dir.glob("*.SMSPEC"))
        unrst_files = list(output_dir.glob("*.UNRST"))

        assert len(smspec_files) > 0, f"No .SMSPEC file generated in {output_dir}"
        assert len(unrst_files) > 0, f"No .UNRST file generated in {output_dir}"


def build_deck_from_spec(spec):
    """Helper to build deck from ModelSpec (imports locally to avoid circular)."""
    from opm_ai.builder.builder import build_deck_from_spec
    return build_deck_from_spec(spec)