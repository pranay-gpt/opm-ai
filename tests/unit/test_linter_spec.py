"""Phase 0 — test that the spec layer loads.

This is the canary: when Phase 3 wires the validator in, this file
expands with one positive + one negative test per spec keyword.

For now it just confirms the schema loads and the WELLDIMS entry has
the expected shape (12 items, default 0 for each, type=int).
"""
from pathlib import Path

import pytest

from opm_ai.linter.spec import load_spec

SPEC_DIR = Path(__file__).resolve().parent.parent.parent / "opm_ai" / "linter" / "spec"


def test_welldims_spec_loads():
    """WELLDIMS spec is present in runspec.yaml and has 12 items."""
    specs = load_spec(SPEC_DIR)
    assert "WELLDIMS" in specs, "WELLDIMS missing from runspec.yaml"
    spec = specs["WELLDIMS"]
    assert spec.section == "RUNSPEC"
    assert spec.required is True
    assert spec.repeated is False
    assert len(spec.items) == 12, f"expected 12 items, got {len(spec.items)}"
    assert spec.items[0].name == "max_wells"
    assert spec.items[0].type == "int"
    assert spec.items[0].default == 0
    assert spec.items[0].range == (0, 100000)


def test_runspec_yaml_loads_as_dict():
    """The YAML loader returns a dict keyed by keyword."""
    specs = load_spec(SPEC_DIR)
    assert isinstance(specs, dict)
    assert all(k.isupper() for k in specs.keys()), "keyword names should be uppercase"


def test_welldims_first_four_items_have_ranges():
    """The first four WELLDIMS items (max-wells, max-conns, max-groups,
    max-wells-per-group) all have inclusive ranges."""
    specs = load_spec(SPEC_DIR)
    spec = specs["WELLDIMS"]
    for i in range(4):
        assert spec.items[i].range is not None, f"item {i} ({spec.items[i].name}) missing range"
        lo, hi = spec.items[i].range
        assert lo <= hi, f"item {i}: invalid range ({lo}, {hi})"


# ---------------------------------------------------------------------- #
# Phase 2 — RUNSPEC keyword coverage tests                                #
# Each test confirms one keyword's spec loaded with the expected shape.  #
# When Phase 3 wires the validator in, these tests get +ve/-ve pairs.    #
# ---------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def runspec_specs():
    """All RUNSPEC specs loaded once per module."""
    from opm_ai.linter.spec import load_spec
    return load_spec(SPEC_DIR)


@pytest.mark.unit
@pytest.mark.parametrize("keyword,expected_items", [
    ("DIMENS", 3),
    ("TABDIMS", 24),
    ("WELLDIMS", 12),
    ("ENDSCALE", 4),   # Phase 3.5 fix: 4 items, not 3 (string kr/pcow + int ntendp/nsendp)
    ("FUNVAR", 1),
])
def test_runspec_keyword_item_count(runspec_specs, keyword, expected_items):
    """Each RUNSPEC keyword has the documented number of items."""
    assert keyword in runspec_specs, f"{keyword} missing from runspec.yaml"
    assert len(runspec_specs[keyword].items) == expected_items, (
        f"{keyword}: expected {expected_items} items, got "
        f"{len(runspec_specs[keyword].items)}"
    )


@pytest.mark.unit
@pytest.mark.parametrize("keyword", ["OIL", "GAS", "WATER", "DISGAS", "VAPOIL", "ECHO", "NOINSPEC"])
def test_runspec_phase_flags_have_no_items(runspec_specs, keyword):
    """Phase-presence flags (OIL/GAS/WATER/DISGAS/VAPOIL/ECHO/NOINSPEC) are bare."""
    assert keyword in runspec_specs
    assert runspec_specs[keyword].items == []


@pytest.mark.unit
def test_dimens_required(runspec_specs):
    """DIMENS is the only RUNSPEC keyword marked required=True (besides WELLDIMS)."""
    assert runspec_specs["DIMENS"].required is True
    assert runspec_specs["WELLDIMS"].required is True


@pytest.mark.unit
def test_fu_nvar_repeatable(runspec_specs):
    """FUNVAR is the only repeatable RUNSPEC keyword (one record per FU_* declaration)."""
    assert runspec_specs["FUNVAR"].repeated is True
    for kw in ("OIL", "GAS", "WATER", "DIMENS", "TABDIMS", "WELLDIMS"):
        assert runspec_specs[kw].repeated is False, f"{kw} should not be repeatable"


@pytest.mark.unit
def test_endscale_item_ranges_inclusive(runspec_specs):
    """ENDSCALE: items 1-2 are string allowed_values, items 3-4 are int ranges.

    Phase 3.5 fix: items 1-2 are scaling-direction keywords
    (NODIR/DIR/REVERS/IRREV/PREV); items 3-4 are int thresholds
    (ntendp ∈ [1, 100], nsendp ∈ [1, 1000]).
    """
    spec = runspec_specs["ENDSCALE"]
    # Items 1-2: string with allowed_values (no range).
    assert spec.items[0].type == "string"
    assert spec.items[0].allowed_values is not None
    assert "NODIR" in spec.items[0].allowed_values
    assert spec.items[1].type == "string"
    assert spec.items[1].allowed_values is not None
    # Items 3-4: int ranges.
    assert spec.items[2].type == "int"
    assert spec.items[2].range == (1, 100)
    assert spec.items[3].type == "int"
    assert spec.items[3].range == (1, 1000)


@pytest.mark.unit
def test_dimens_range_is_positive(runspec_specs):
    """DIMENS nx/ny/nz must all be positive (lower bound is 1, not 0)."""
    spec = runspec_specs["DIMENS"]
    for item in spec.items:
        assert item.range[0] >= 1, f"{item.name}: nx/ny/nz must be >= 1"


@pytest.mark.unit
def test_tabdims_defaults(runspec_specs):
    """TABDIMS items default to 0 or 1 depending on whether OPM Flow assumes a region.

    Items 3, 4, 5 (max_pvt_regions, max_saturation_regions, max_equil_regions)
    default to 1 because OPM Flow assumes at least 1 region by default. All
    other items default to 0 per the manual.
    """
    spec = runspec_specs["TABDIMS"]
    one_defaults = {"max_pvt_regions", "max_saturation_regions", "max_equil_regions"}
    for item in spec.items:
        if item.name in one_defaults:
            assert item.default == 1, f"{item.name}: expected default 1, got {item.default}"
        else:
            assert item.default == 0, f"{item.name}: expected default 0, got {item.default}"
