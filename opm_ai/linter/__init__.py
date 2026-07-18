"""opm_ai.linter - Offline-first OPM Flow deck linter."""

from opm_ai.linter.deck import Deck
from opm_ai.linter.linter import lint_deck
from opm_ai.linter.models import LintIssue, LintResult

__all__ = ["Deck", "lint_deck", "LintResult", "LintIssue"]