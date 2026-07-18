"""Linter module for OPM Flow deck validation."""

from opm_ai.linter.deck import Deck, LintResult, LintError
from opm_ai.linter.linter import lint_deck

__all__ = ["Deck", "LintResult", "LintError", "lint_deck"]