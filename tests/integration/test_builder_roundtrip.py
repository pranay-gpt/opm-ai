"""Integration test: build a deck with build_deck(), write to temp file,
run flow --check (or full Flow run), assert Flow accepts it without errors.

This test documents known defect #1 from STATUS.md:
base.j2 line 1 has a stray Python docstring that renders into the .DATA file,
causing Flow to reject it with "String \"\"\"...\"\" not formatted as valid keyword".

Marked xfail until base.j2 is fixed (docstring removed from template).
"""
import pytest
import tempfile
from pathlib import Path

from opm_ai.builder.builder import build_deck


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.xfail(reason="base.j2 has stray docstring, see STATUS.md defect #1")
def test_build_deck_roundtrip_flow_check(tmp_path):
    """Build a deck, write to temp file, run flow --check, assert it passes."""
    desc = "10x10x5 grid, simple depletion, one producer"

    # Build the deck
    deck_string, lint_result = build_deck(desc, output_path=None)

    # Verify linting passes (builder's internal lint)
    assert lint_result.passed, f"Builder lint failed: {lint_result.errors}"
    assert "RUNSPEC" in deck_string
    assert "GRID" in deck_string
    assert "PROPS" in deck_string
    assert "SCHEDULE" in deck_string

    # Write to temp file for Flow check
    deck_path = tmp_path / "generated.DATA"
    deck_path.write_text(deck_string)

    # Run flow --check on the generated deck
    import subprocess
    result = subprocess.run(
        ["flow", "--check", str(deck_path)],
        capture_output=True,
        text=True,
        timeout=60
    )

    # Flow should accept the deck (exit code 0, no error output)
    assert result.returncode == 0, (
        f"flow --check failed with exit code {result.returncode}.\n"
        f"STDOUT: {result.stdout}\n"
        f"STDERR: {result.stderr}\n"
        f"Deck content (first 2000 chars):\n{deck_string[:2000]}"
    )

    # Also verify no error messages in stderr
    assert "ERROR" not in result.stderr.upper(), (
        f"flow --check produced errors:\n{result.stderr}"
    )
    assert "String" not in result.stderr and "keyword" not in result.stderr.lower(), (
        f"flow --check rejected deck (likely stray docstring in base.j2):\n{result.stderr}"
    )


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.xfail(reason="base.j2 has stray docstring, see STATUS.md defect #1")
def test_build_deck_roundtrip_flow_full_run(tmp_path):
    """Build a deck, write to temp file, run full flow simulation, assert it completes."""
    desc = "10x10x5 grid, simple depletion, one producer"

    # Build the deck
    deck_string, lint_result = build_deck(desc, output_path=None)
    assert lint_result.passed, f"Builder lint failed: {lint_result.errors}"

    # Write to temp file
    deck_path = tmp_path / "generated.DATA"
    deck_path.write_text(deck_string)

    # Create output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Run full flow simulation
    import subprocess
    result = subprocess.run(
        ["flow", str(deck_path)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(output_dir)
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
@pytest.mark.xfail(reason="base.j2 has stray docstring, see STATUS.md defect #1")
def test_build_deck_simple_depletion_passes_flow_check(tmp_path):
    """Test a simple depletion case specifically (SPE1-like)."""
    desc = "Simple depletion case, 10x10x5 grid, one producer at (5,5,1)"

    deck_string, lint_result = build_deck(desc)
    assert lint_result.passed

    deck_path = tmp_path / "depletion.DATA"
    deck_path.write_text(deck_string)

    import subprocess
    result = subprocess.run(
        ["flow", "--check", str(deck_path)],
        capture_output=True,
        text=True,
        timeout=60
    )

    assert result.returncode == 0, (
        f"flow --check failed: {result.returncode}\n"
        f"STDERR: {result.stderr}"
    )


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.xfail(reason="base.j2 has stray docstring, see STATUS.md defect #1")
def test_build_deck_injection_passes_flow_check(tmp_path):
    """Test an injection case passes flow --check."""
    desc = "10x10x5 grid, water injection, one injector and one producer"

    deck_string, lint_result = build_deck(desc)
    assert lint_result.passed

    deck_path = tmp_path / "injection.DATA"
    deck_path.write_text(deck_string)

    import subprocess
    result = subprocess.run(
        ["flow", "--check", str(deck_path)],
        capture_output=True,
        text=True,
        timeout=60
    )

    assert result.returncode == 0, (
        f"flow --check failed for injection case: {result.returncode}\n"
        f"STDERR: {result.stderr}"
    )