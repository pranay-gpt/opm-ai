"""Integration test: build a deck with build_deck(), write to temp file,
validate with flow (dry-run or full run), assert Flow accepts it without errors.

Validation command: `flow --enable-dry-run=true --output-dir=DIR DECK`.
Note: bare `flow --check DECK` does NOT work in OPM Flow 2026.04 - the
--check parameter requires a value (--check=true) and is not the deck
validation mode; --enable-dry-run=true is (parses deck, builds config,
skips simulation; exit 0 = valid deck).

This test also documents known defect #1 from STATUS.md:
base.j2 line 1 had a stray Python docstring that rendered into the .DATA file,
causing Flow to reject it with "String \"\"\"...\"\" not formatted as valid keyword".
This defect is now FIXED - the docstring has been removed from the template.
"""
import subprocess

import pytest

from opm_ai.builder.builder import build_deck


def _flow_dry_run(deck_path, output_dir):
    """Run flow in dry-run (validation) mode; returns CompletedProcess."""
    output_dir.mkdir(exist_ok=True)
    return subprocess.run(
        [
            "flow",
            "--enable-dry-run=true",
            f"--output-dir={output_dir}",
            str(deck_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.integration
@pytest.mark.slow
def test_build_deck_roundtrip_flow_check(tmp_path):
    """Build a deck, write to temp file, run flow dry-run, assert it passes."""
    desc = "10x10x5 grid, simple depletion, one producer"

    # Build the deck
    deck_string, lint_result = build_deck(desc, output_path=None)

    # Verify linting passes (builder's internal lint)
    assert lint_result.passed, f"Builder lint failed: {lint_result.errors}"
    assert "RUNSPEC" in deck_string
    assert "GRID" in deck_string
    assert "PROPS" in deck_string
    assert "SCHEDULE" in deck_string

    # Write to temp file for Flow validation
    deck_path = tmp_path / "GENERATED.DATA"
    deck_path.write_text(deck_string)

    result = _flow_dry_run(deck_path, tmp_path / "out")

    # Flow should accept the deck (exit code 0, no error output)
    assert result.returncode == 0, (
        f"flow dry-run failed with exit code {result.returncode}.\n"
        f"STDOUT: {result.stdout}\n"
        f"STDERR: {result.stderr}\n"
        f"Deck content (first 2000 chars):\n{deck_string[:2000]}"
    )

    # Also verify no error messages in stderr
    assert "ERROR" not in result.stderr.upper(), (
        f"flow dry-run produced errors:\n{result.stderr}"
    )
    assert "String" not in result.stderr, (
        f"flow dry-run rejected deck (likely stray docstring in base.j2):\n{result.stderr}"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_build_deck_roundtrip_flow_full_run(tmp_path):
    """Build a deck, write to temp file, run full flow simulation, assert it completes."""
    desc = "10x10x5 grid, simple depletion, one producer"

    # Build the deck
    deck_string, lint_result = build_deck(desc, output_path=None)
    assert lint_result.passed, f"Builder lint failed: {lint_result.errors}"

    # Write to temp file
    deck_path = tmp_path / "GENERATED.DATA"
    deck_path.write_text(deck_string)

    # Create output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Run full flow simulation (--output-dir, not cwd: flow writes next to
    # the deck by default regardless of working directory)
    result = subprocess.run(
        ["flow", f"--output-dir={output_dir}", str(deck_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )

    # Flow should complete successfully (exit code 0)
    assert result.returncode == 0, (
        f"flow simulation failed with exit code {result.returncode}.\n"
        f"STDOUT: {result.stdout}\n"
        f"STDERR: {result.stderr}\n"
        f"Deck content (first 2000 chars):\n{deck_string[:2000]}"
    )

    # Check for key output files (SMSPEC and UNRST should exist)
    smspec_files = list(output_dir.glob("*.SMSPEC"))
    unrst_files = list(output_dir.glob("*.UNRST"))

    assert len(smspec_files) > 0, (
        f"No .SMSPEC file generated in {output_dir}. "
        f"STDERR: {result.stderr}"
    )
    assert len(unrst_files) > 0, (
        f"No .UNRST file generated in {output_dir}. "
        f"STDERR: {result.stderr}"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_build_deck_simple_depletion_passes_flow_check(tmp_path):
    """Test a simple depletion case specifically (SPE1-like)."""
    desc = "Simple depletion case, 10x10x5 grid, one producer at (5,5,1)"

    deck_string, lint_result = build_deck(desc)
    assert lint_result.passed, f"Builder lint failed: {lint_result.errors}"

    deck_path = tmp_path / "DEPLETION.DATA"
    deck_path.write_text(deck_string)

    result = _flow_dry_run(deck_path, tmp_path / "out")

    assert result.returncode == 0, (
        f"flow dry-run failed: {result.returncode}\n"
        f"STDERR: {result.stderr}"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_build_deck_injection_passes_flow_check(tmp_path):
    """Test an injection case passes flow dry-run validation."""
    desc = "10x10x5 grid, water injection, one injector and one producer"

    deck_string, lint_result = build_deck(desc)
    assert lint_result.passed, f"Builder lint failed: {lint_result.errors}"

    deck_path = tmp_path / "INJECTION.DATA"
    deck_path.write_text(deck_string)

    result = _flow_dry_run(deck_path, tmp_path / "out")

    assert result.returncode == 0, (
        f"flow dry-run failed for injection case: {result.returncode}\n"
        f"STDERR: {result.stderr}"
    )
