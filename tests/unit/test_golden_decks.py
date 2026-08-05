"""Golden-file tests for the builder.

These tests pin the byte-exact deck output for each of the 8 scenarios in
`ScenarioType`. The contract: the deck generated for each scenario must be
byte-identical to the committed fixture under `tests/fixtures/golden/`.

Why this exists: Phase 2 Stage 3.3 refactors the template layer (adds
{% block %} markers, wires a dispatch loader). The refactor is only correct
if it produces byte-identical output for every scenario. The fixtures were
recorded against the current `base.j2` and exist to catch any drift the
refactor introduces.

To re-record (after an intentional change to the template or builder):
    python tests/unit/record_golden_decks.py

The test runs against `build_deck(description)`, which goes through the
full extraction + template render pipeline. Whitespace, line ordering, and
case matter: the test compares full bytes, not semantic equivalence.

Marked @pytest.mark.slow so it does not run on every save.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from opm_ai.builder.builder import build_deck

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

# Description strings that trigger each scenario. Source:
# tests/integration/test_dataset_validation.py (the canonical set).
# The fixture filename matches `ScenarioType.value`.
SCENARIO_DESCRIPTIONS = {
    "DEPLETION":             "10x10x3 grid, simple depletion, one producer",
    "WATERFLOOD_5SPOT":      "10x10x3 grid, waterflood five spot",
    "WATERFLOOD_LINE_DRIVE": "10x10x3 grid, line drive water injection",
    "WAG":                   "wag injection on a 15x15x3 grid",
    "GAS_CAP":               "gas cap reservoir, 10x10x3 grid",
    "CO2_EOR":               "co2 eor flood, 10x10x3 grid",
    "BUILDUP":               "pressure buildup test, 10x10x3 grid",
    "MULTILAYER":            "multilayer reservoir, 12x12x4 grid",
}


@pytest.mark.unit
@pytest.mark.slow
@pytest.mark.parametrize("scenario_value", sorted(SCENARIO_DESCRIPTIONS.keys()))
def test_golden_deck_byte_identical(scenario_value):
    """The current builder produces a deck byte-identical to the committed fixture."""
    fixture = GOLDEN_DIR / f"{scenario_value}.DATA"
    if not fixture.exists():
        pytest.skip(f"golden fixture missing: {fixture}")

    desc = SCENARIO_DESCRIPTIONS[scenario_value]
    deck, lint = build_deck(desc)

    # The lint pass is not the contract here, but a regression guard: if a
    # refactor produces a deck that does not lint clean, the golden test
    # is the wrong place to find out.
    assert lint.passed, (
        f"builder produced a deck that fails lint for {scenario_value}: "
        f"{[e.message for e in lint.errors]}"
    )

    committed = fixture.read_text(encoding="utf-8")
    if committed != deck:
        # Write the diff side-by-side for human inspection.
        diff_path = GOLDEN_DIR / f"{scenario_value}.DATA.fresh"
        diff_path.write_text(deck, encoding="utf-8")
        pytest.fail(
            f"golden drift in {scenario_value} ({len(committed)} -> {len(deck)} bytes). "
            f"Inspect {diff_path} for the current output. "
            f"If intentional, run tests/unit/record_golden_decks.py"
        )


@pytest.mark.unit
def test_golden_fixtures_exist_for_all_scenarios():
    """All 8 scenarios have committed fixtures."""
    missing = [
        s for s in SCENARIO_DESCRIPTIONS
        if not (GOLDEN_DIR / f"{s}.DATA").exists()
    ]
    assert not missing, f"missing golden fixtures: {missing}"


@pytest.mark.unit
def test_golden_fixtures_are_nonempty():
    """Each fixture is non-trivial (catches accidental truncation)."""
    for scenario_value in SCENARIO_DESCRIPTIONS:
        fixture = GOLDEN_DIR / f"{scenario_value}.DATA"
        if not fixture.exists():
            continue
        size = fixture.stat().st_size
        assert size > 1000, f"{fixture} suspiciously small ({size} bytes)"