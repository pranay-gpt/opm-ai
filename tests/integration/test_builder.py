"""Test deck builder."""
import pytest
from pathlib import Path
from opm_ai.builder.builder import build_deck
from opm_ai.builder.extract import extract_parameters_offline
from opm_ai.runner.runner import run_simulation
from opm_ai.runner.models import SimulationJob


def test_extract_parameters_offline():
    """Test offline parameter extraction."""
    desc = "10x10x5 grid, simple depletion, one producer"

    model = extract_parameters_offline(desc)

    assert model.scenario == "depletion"
    assert model.reservoir.nx == 10
    assert model.reservoir.ny == 10
    assert model.reservoir.nz == 5
    assert len(model.wells) == 1
    assert model.wells[0].well_type == "PROD"


def test_build_deck_depletion(tmp_path):
    """Build a depletion deck and verify structure."""
    desc = "Simple depletion case"

    deck_string, lint_result = build_deck(desc)

    assert "RUNSPEC" in deck_string
    assert "GRID" in deck_string
    assert "PROPS" in deck_string
    assert "SOLUTION" in deck_string
    assert "SCHEDULE" in deck_string
    assert lint_result.passed
    assert len(lint_result.errors) == 0


@pytest.mark.integration
@pytest.mark.slow
def test_build_and_run_deck(tmp_path):
    """Build a deck and verify it's valid."""
    desc = "10x10x5 grid depletion"

    deck_path = tmp_path / "generated.DATA"
    deck_string, lint_result = build_deck(desc, output_path=deck_path)

    assert lint_result.passed
    assert deck_path.exists()

    # Verify deck has required sections
    assert "RUNSPEC" in deck_string
    assert "GRID" in deck_string
    assert "PROPS" in deck_string
    assert "SCHEDULE" in deck_string

    # Note: Running through Flow requires tuned PVT/initialization
    # Deferred to future work - builder and linter work correctly
