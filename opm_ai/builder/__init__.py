"""Builder module for generating OPM Flow decks from natural language descriptions."""

from pathlib import Path
from typing import Optional

from opm_ai.builder.builder import build_deck as _build_deck
from opm_ai.builder.models import ModelSpec, ReservoirSpec, WellSpec, WellType
from opm_ai.builder.extract import extract_parameters_offline
from opm_ai.linter import lint_deck, LintResult


def build_deck(
    description: str,
    output_path: Optional[Path] = None,
) -> tuple[str, LintResult]:
    """
    Build an OPM Flow deck from natural language description.

    Args:
        description: Natural language description of the model.
        output_path: Optional path to write the deck file.

    Returns:
        Tuple of (deck_string, LintResult).
    """
    return _build_deck(description, output_path)


__all__ = ["build_deck"]