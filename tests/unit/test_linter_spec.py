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
