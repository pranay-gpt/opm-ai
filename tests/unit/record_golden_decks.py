"""Re-record the golden deck fixtures.

Run this script after an intentional change to the template, the builder,
or the scenario extraction. It regenerates the 8 fixtures under
tests/fixtures/golden/ from the current builder output.

Usage:
    python tests/unit/record_golden_decks.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from opm_ai.builder.builder import build_deck

GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "golden"

SCENARIOS = [
    ("DEPLETION",             "10x10x3 grid, simple depletion, one producer"),
    ("WATERFLOOD_5SPOT",      "10x10x3 grid, waterflood five spot"),
    ("WATERFLOOD_LINE_DRIVE", "10x10x3 grid, line drive water injection"),
    ("WAG",                   "wag injection on a 15x15x3 grid"),
    ("GAS_CAP",               "gas cap reservoir, 10x10x3 grid"),
    ("CO2_EOR",               "co2 eor flood, 10x10x3 grid"),
    ("BUILDUP",               "pressure buildup test, 10x10x3 grid"),
    ("MULTILAYER",            "multilayer reservoir, 12x12x4 grid"),
]


def main() -> int:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for scenario_value, desc in SCENARIOS:
        deck, lint = build_deck(desc)
        if not lint.passed:
            print(f"  WARN {scenario_value}: lint failed before recording")
        fixture = GOLDEN_DIR / f"{scenario_value}.DATA"
        fixture.write_text(deck, encoding="utf-8")
        print(f"  recorded {fixture.name}: {len(deck)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())