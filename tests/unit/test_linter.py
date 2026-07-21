"""Test deck parser and linter."""
import pytest
from pathlib import Path
from opm_ai.linter.deck import Deck
from opm_ai.linter.linter import lint_deck


def test_parse_spe1_deck(spe1_deck):
    """Parse SPE1 fixture and check structure."""
    deck_path = spe1_deck
    assert deck_path.exists()

    deck = Deck(deck_path)

    # Should have major sections
    assert len(deck.sections) > 0

    # Should have RUNSPEC
    runspec = deck.get_section("RUNSPEC")
    assert runspec is not None

    # Should have GRID
    grid = deck.get_section("GRID")
    assert grid is not None


def test_lint_spe1_deck(spe1_deck):
    """Lint SPE1 fixture."""
    deck_path = spe1_deck

    result = lint_deck(deck_path)

    assert result is not None
    assert result.deck_path == str(deck_path)
    # SPE1 should have no errors (it's a valid reference deck)
    assert len(result.errors) == 0


def test_lint_sample_deck(tmp_path):
    """Lint a minimal sample deck."""
    deck_content = """
RUNSPEC

DIMENS
  10 10 5 /

METRIC

GRID

DX
  500*100 /

DY
  500*100 /

DZ
  500*10 /

TOPS
  500*3000 /

PORO
  500*0.2 /

PERMX
  500*100 /

PROPS

SCHEDULE
"""
    deck_file = tmp_path / "test.DATA"
    deck_file.write_text(deck_content)

    result = lint_deck(deck_file)

    assert result.passed
    assert len(result.errors) == 0
