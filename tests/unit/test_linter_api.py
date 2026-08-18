"""LinterAPI sync entry-point tests."""
from pathlib import Path

import pytest

from opm_ai.linter.api import LinterAPI, default_api


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "linter_api"


def test_lint_returns_lint_result_on_clean_deck():
    result = default_api.lint(FIXTURE_DIR / "clean.DATA")
    assert result.deck_path.endswith("clean.DATA")
    assert result.passed is True
    assert len(result.errors) == 0


def test_lint_unknown_keyword_yields_error():
    result = default_api.lint(FIXTURE_DIR / "parse_error.DATA")
    assert result.passed is False
    assert len(result.errors) >= 1


def test_lint_missing_required_sections_warns_or_errors():
    result = default_api.lint(FIXTURE_DIR / "missing_sections.DATA")
    # GRID and SCHEDULE missing -> ERROR (no INCLUDE present).
    assert len(result.errors) >= 1
    severities = {i.severity for i in result.issues}
    assert "ERROR" in severities


def test_lint_returns_deepcopy_per_call():
    a = default_api.lint(FIXTURE_DIR / "clean.DATA")
    b = default_api.lint(FIXTURE_DIR / "clean.DATA")
    assert a is not b
    a.issues.append("mutated")
    assert len(b.issues) == len(a.issues) - 1


def test_invalidate_cache_clears_stats():
    api = LinterAPI()
    api.lint(FIXTURE_DIR / "clean.DATA")  # warm
    api.lint(FIXTURE_DIR / "clean.DATA")  # hit
    s_before = api.cache_stats()
    api.invalidate_cache()
    s_after = api.cache_stats()
    assert s_before.size > 0
    assert s_after.size == 0
