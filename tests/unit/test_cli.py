"""Test CLI commands."""
import pytest
from pathlib import Path
from click.testing import CliRunner
from opm_ai.cli import main


def test_cli_help():
    """Test CLI help output."""
    runner = CliRunner()
    result = runner.invoke(main, ['--help'])
    assert result.exit_code == 0
    assert "OPM-AI" in result.output


def test_cli_lint_spe1(spe1_deck):
    """Test CLI lint command on SPE1."""
    runner = CliRunner()
    spe1_path = spe1_deck
    result = runner.invoke(main, ['lint', str(spe1_path)])
    assert result.exit_code == 0
    assert "Passed" in result.output


def test_cli_build(tmp_path):
    """Test CLI build command."""
    runner = CliRunner()
    output_file = tmp_path / "cli_test.DATA"
    result = runner.invoke(main, ['build', '5x5x3 depletion', '-o', str(output_file)])
    assert result.exit_code == 0
    assert output_file.exists()
    assert "Lint passed" in result.output
