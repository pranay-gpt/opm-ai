"""Builder module for generating OPM Flow decks from natural language descriptions."""

from pathlib import Path
from typing import Optional

from opm_ai.builder.builder import build_deck as _build_deck
from opm_ai.builder.models import ModelSpec, ReservoirSpec, WellSpec, WellType
from opm_ai.builder.extract import (
    extract_parameters_offline,
    extract_parameters_offline_with_provenance,
)
from opm_ai.linter import lint_deck, LintResult
from opm_ai.preprocess import FluidDescriptor


def build_deck(
    description: str,
    output_path: Optional[Path] = None,
    use_llm: bool = False,
    fluid: Optional[FluidDescriptor] = None,
) -> tuple[str, LintResult]:
    """
    Build an OPM Flow deck from natural language description.

    Args:
        description: Natural language description of the model.
        output_path: Optional path to write the deck file.
        use_llm: Whether to use LLM for parameter extraction (requires API key)
        fluid: Optional FluidDescriptor for fluid-specific PVT tables

    Returns:
        Tuple of (deck_string, LintResult).
    """
    return _build_deck(description, output_path, use_llm, fluid)


# F6.4/F6.7/F6.8 audit fix: __all__ documents and enforces the public
# surface of the builder package. Routes and tests should import from
# `opm_ai.builder` only what is listed here. Internal helpers live in
# `opm_ai.builder.extract` and are not part of the stable API.
__all__ = [
    "build_deck",
    "extract_parameters_offline",
    "extract_parameters_offline_with_provenance",
    "FluidDescriptor",
    "LintResult",
    "ModelSpec",
    "ReservoirSpec",
    "WellSpec",
    "WellType",
]