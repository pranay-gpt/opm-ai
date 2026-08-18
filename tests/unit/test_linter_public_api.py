"""Pin the public import surface of opm_ai.linter.

If any of these symbols stops importing, downstream callers break.
Touching this test means a deliberate API change.
"""
import pytest


def test_public_imports_resolve():
    # All of these MUST resolve from opm_ai.linter without error.
    from opm_ai.linter import (
        Deck,
        lint_deck,
        lint_deck_combined,
        lint_deck_v2,
        LintResult,
        LintIssue,
    )
    assert callable(lint_deck)
    assert callable(lint_deck_combined)
    assert callable(lint_deck_v2)


def test_linter_api_module_imports():
    # The new facade module exists and exports its public types.
    from opm_ai.linter.api import (
        LinterAPI,
        LinterError,
        LinterTimeoutError,
        CacheStats,
        default_api,
        lint_deck as api_lint_deck,
    )
    assert isinstance(default_api, LinterAPI)
    assert api_lint_deck is not None  # may be the same symbol as opm_ai.linter.lint_deck
