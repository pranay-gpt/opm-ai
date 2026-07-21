"""Stage D ground truth: the 5 distinct scenario decks run in OPM Flow.

Each scenario deck must pass flow dry-run (exit 0) AND complete a short real
run. Physics sanity is asserted loosely from the summary output:
- buildup: WBHP rises after shut-in
- gas cap: FGOR climbs above the solution GOR early in the run
- WAG: alternation is asserted on deck text (cheap); the run must complete

Grids are small (10x10x3) and runs finish in well under a second each, so
these stay inside the standard slow/integration markers.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from opm_ai.builder.builder import build_deck
from opm_ai.postprocess.summary import read_summary

flow_missing = shutil.which("flow") is None

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(flow_missing, reason="flow binary not installed"),
]


def _run_flow(deck_string: str, tmp_path: Path) -> Path:
    """Dry-run then real-run a deck; return the real-run output dir."""
    deck_path = tmp_path / "CASE.DATA"
    deck_path.write_text(deck_string)
    dry = tmp_path / "dry"
    dry.mkdir()
    result = subprocess.run(
        ["flow", "--enable-dry-run=true", f"--output-dir={dry}", str(deck_path)],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, f"dry-run failed:\n{result.stderr[-2000:]}"

    out = tmp_path / "out"
    out.mkdir()
    result = subprocess.run(
        ["flow", f"--output-dir={out}", str(deck_path)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"real run failed:\n{result.stderr[-2000:]}"
    return out


def test_wag_run_completes(tmp_path):
    """WAG deck (alternating WCONINJE half-cycles via DATES) runs to the end."""
    deck, lint = build_deck("wag injection on a 10x10x3 grid")
    assert lint.passed
    out = _run_flow(deck, tmp_path)
    df = read_summary(out)
    assert not df.empty
    # 3x30d water + 7 quarterly DATES half-cycles = 731 days (1 JAN 2017)
    assert df["TIME"].iloc[-1] >= 725
    # Both fluids actually injected at some point
    assert df["WWIR:INJ"].max() > 0
    assert df["WGIR:INJ"].max() > 0


def test_buildup_wbhp_rises_after_shut_in(tmp_path):
    """Buildup: WBHP at the end of the buildup exceeds end-of-flow WBHP."""
    deck, lint = build_deck("pressure buildup test, 10x10x3 grid")
    assert lint.passed
    out = _run_flow(deck, tmp_path)
    df = read_summary(out)
    assert not df.empty
    wbhp = df["WBHP:PROD"]
    flowing = df[df["TIME"] <= 180.0]
    end_of_flow = flowing["WBHP:PROD"].iloc[-1]
    end_of_buildup = wbhp.iloc[-1]
    assert end_of_buildup > end_of_flow + 50.0, (
        f"WBHP must rise during buildup: {end_of_flow:.0f} -> {end_of_buildup:.0f}"
    )


def test_gas_cap_gor_above_solution_gor(tmp_path):
    """Gas cap: producing GOR exceeds the solution GOR (1.27 Mscf/stb) early."""
    deck, lint = build_deck("gas cap reservoir, 10x10x3 grid")
    assert lint.passed
    out = _run_flow(deck, tmp_path)
    df = read_summary(out)
    assert not df.empty
    first_year = df[df["TIME"] <= 400.0]
    assert (first_year["FGOR"] > 1.28).any(), (
        f"gas-cap deck should show FGOR above solution GOR, max={df['FGOR'].max():.3f}"
    )


def test_co2_run_completes_with_gas_injection(tmp_path):
    """CO2 EOR deck (dense PVDG, gas injector) completes with gas injected."""
    deck, lint = build_deck("co2 eor flood, 10x10x3 grid")
    assert lint.passed
    out = _run_flow(deck, tmp_path)
    df = read_summary(out)
    assert not df.empty
    assert df["WGIR:INJ"].max() > 0


def test_multilayer_run_completes(tmp_path):
    """Multilayer deck (500/50/200 md contrast) completes."""
    deck, lint = build_deck("multilayer reservoir, 10x10x3 grid")
    assert lint.passed
    out = _run_flow(deck, tmp_path)
    df = read_summary(out)
    assert not df.empty
    assert df["FOPT"].iloc[-1] > 0
