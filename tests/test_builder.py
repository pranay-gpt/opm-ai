# tests/test_builder.py
"""
Unit tests for opm_ai.builder.

All tests run fully offline (no LLM, no Flow binary).
Run with: python -m pytest tests/test_builder.py -v
"""
import pytest
from opm_ai.builder import (
    build_deck, build_from_description,
    ReservoirDescription, WellSpec, FluidSystem, BuildResult,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _default_desc() -> ReservoirDescription:
    return ReservoirDescription(
        title="Test Reservoir",
        nx=10, ny=10, nz=3,
        dx=100.0, dy=100.0, dz=10.0,
        depth_top=2000.0,
        porosity=0.20,
        permeability=100.0,
        fluid_system=FluidSystem.OIL_WATER,
        p_init=350.0,
        swi=0.20,
        sim_years=5.0,
        report_freq="monthly",
        wells=[
            WellSpec(name="PROD1", type="PRODUCER", i=5, j=5, k1=1, k2=3,
                     control="BHP", bhp_limit=100.0),
            WellSpec(name="INJ1",  type="INJECTOR", i=1, j=1, k1=1, k2=3,
                     inj_fluid="WATER", inj_rate=200.0, inj_bhp_max=400.0),
        ]
    )


# ── Tests ───────────────────────────────────────────────────────────────────

def test_build_from_description_returns_build_result():
    """build_from_description always returns a BuildResult."""
    result = build_from_description(_default_desc())
    assert isinstance(result, BuildResult)


def test_deck_contains_required_sections():
    """Generated deck must contain all 5 required OPM sections."""
    result = build_from_description(_default_desc())
    for section in ["RUNSPEC", "GRID", "PROPS", "SOLUTION", "SCHEDULE"]:
        assert section in result.deck_text, f"{section} missing from generated deck"


def test_deck_ends_with_end():
    """Generated deck must end with END keyword."""
    result = build_from_description(_default_desc())
    assert "END" in result.deck_text


def test_lint_passed_on_valid_description():
    """A fully specified description should produce a lint-passing deck."""
    result = build_from_description(_default_desc())
    assert result.lint_passed, (
        f"Expected lint to pass. Warnings: {result.warnings}"
    )


def test_well_names_in_deck():
    """Well names from the description must appear in the deck."""
    result = build_from_description(_default_desc())
    assert "PROD1" in result.deck_text
    assert "INJ1"  in result.deck_text


def test_dimens_matches_description():
    """DIMENS in deck must match the nx/ny/nz from the description."""
    desc = _default_desc()
    result = build_from_description(desc)
    assert f"{desc.nx}  {desc.ny}  {desc.nz}" in result.deck_text


def test_black_oil_includes_pvto():
    """Black-oil fluid system must render PVTO and PVDG tables."""
    desc = _default_desc()
    desc.fluid_system = FluidSystem.BLACK_OIL
    result = build_from_description(desc)
    assert "PVTO" in result.deck_text
    assert "PVDG" in result.deck_text


def test_oil_water_uses_pvcdo():
    """Oil-water fluid system must render PVCDO (dead oil), not PVTO."""
    result = build_from_description(_default_desc())
    assert "PVCDO" in result.deck_text
    assert "PVTO"  not in result.deck_text


def test_tstep_count_monthly():
    """Monthly reporting over 5 years = 60 time steps."""
    result = build_from_description(_default_desc())
    # Template renders: 60*30
    assert "60*30" in result.deck_text


def test_build_deck_no_llm_returns_build_result():
    """build_deck with use_llm=False must return a BuildResult."""
    result = build_deck(
        "A simple sandstone reservoir with one producer",
        use_llm=False,
    )
    assert isinstance(result, BuildResult)
    assert len(result.deck_text) > 100


def test_build_result_has_summary():
    """BuildResult.lint_summary must always be a non-empty string."""
    result = build_from_description(_default_desc())
    assert isinstance(result.lint_summary, str)
    assert len(result.lint_summary) > 0
