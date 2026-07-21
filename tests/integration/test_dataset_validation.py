"""Dataset validation tests.

Two directions of ground truth:
1. Builder scenarios: every supported scenario type must produce a deck that
   lints clean AND passes flow dry-run validation (exit 0).
2. Fixture decks: known-good SPE decks that Flow accepts must NOT be
   rejected by the linter (guards against false-positive strictness).

Validation command is `flow --enable-dry-run=true --output-dir=DIR DECK`
(bare `flow --check` is rejected by flow 2026.04).
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from opm_ai.builder.builder import build_deck
from opm_ai.linter.linter import lint_deck

FIXTURES = Path(__file__).parent.parent / "fixtures"

flow_missing = shutil.which("flow") is None

SCENARIO_DESCS = [
    pytest.param("10x10x3 grid, simple depletion, one producer", id="depletion-spe1-grid"),
    pytest.param("10x10x5 grid, simple depletion, one producer", id="depletion-5-layers"),
    pytest.param("20x20x4 grid, depletion, one producer", id="depletion-20x20x4"),
    pytest.param("5x5x1 grid, depletion", id="depletion-single-layer"),
    pytest.param("10x10x3 grid, waterflood five spot", id="waterflood-5spot"),
    pytest.param("15x15x3 waterflood five spot", id="waterflood-15x15"),
    pytest.param("10x10x3 grid, line drive water injection", id="line-drive"),
    pytest.param("10x10x5 grid, water injection, one injector and one producer", id="injector-producer"),
    pytest.param("just a simple oil reservoir", id="default-no-grid"),
    # Stage D distinct scenario templates
    pytest.param("wag injection on a 15x15x3 grid", id="wag"),
    pytest.param("gas cap reservoir, 10x10x3 grid", id="gas-cap"),
    pytest.param("co2 eor flood, 10x10x3 grid", id="co2-eor"),
    pytest.param("pressure buildup test, 10x10x3 grid", id="buildup"),
    pytest.param("multilayer reservoir, 12x12x4 grid", id="multilayer"),
]

# Known-good decks: Flow 2026.04 accepts all of these (verified via dry-run).
# The linter must not reject them. Selected to cover: multi-well WELSPECS,
# family II saturation functions (GASWATER), two-phase (OILGAS), VAPOIL+PVTG
# (SPE3), INCLUDE-based GRID (SPE9), COPY/inline-'/' comments (WCONPROD).
KNOWN_GOOD_FIXTURES = [
    "spe1/SPE1CASE1.DATA",
    "spe1/SPE1CASE2.DATA",
    "spe1/SPE1CASE2_OILGAS.DATA",
    "spe1/SPE1CASE2_GASWATER.DATA",
    "spe3/SPE3CASE1.DATA",
    "spe9/SPE9.DATA",
    "wconprod/WCONPROD-00.DATA",
    "wconprod/WCONPROD-06.DATA",
    "wconprod/WCONPROD-12.DATA",
]


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(flow_missing, reason="flow binary not installed")
@pytest.mark.parametrize("desc", SCENARIO_DESCS)
def test_scenario_deck_lints_and_validates(tmp_path, desc):
    """Every supported scenario builds a deck that lints clean and Flow accepts."""
    deck_string, lint_result = build_deck(desc)
    assert lint_result.passed, (
        f"lint failed for {desc!r}: {[e.message for e in lint_result.errors]}"
    )

    deck_path = tmp_path / "CASE.DATA"
    deck_path.write_text(deck_string)
    out = tmp_path / "out"
    out.mkdir()

    result = subprocess.run(
        ["flow", "--enable-dry-run=true", f"--output-dir={out}", str(deck_path)],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, (
        f"flow rejected deck for {desc!r} (exit {result.returncode}).\n"
        f"STDERR: {result.stderr[-2000:]}"
    )


@pytest.mark.unit
@pytest.mark.parametrize("rel_path", KNOWN_GOOD_FIXTURES)
def test_linter_accepts_known_good_fixture(rel_path):
    """The linter must not reject decks that Flow itself accepts."""
    deck_path = FIXTURES / rel_path
    if not deck_path.exists():
        pytest.skip(f"fixture {rel_path} not present")

    result = lint_deck(deck_path)
    assert result.passed, (
        f"linter false-positive on known-good {rel_path}: "
        f"{[(e.rule_id, e.message) for e in result.errors]}"
    )
