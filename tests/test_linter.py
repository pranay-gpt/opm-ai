# tests/test_linter.py
"""
Unit tests for opm_ai.linter.

All tests run fully offline (no LLM calls, no Flow binary needed).
Run with: python -m pytest tests/test_linter.py -v
"""
import pytest
from opm_ai.linter import lint_deck, LintResult, DiagnosticSeverity


# ── Fixtures ──────────────────────────────────────────────────────────────────

MINIMAL_VALID_DECK = """
RUNSPEC
TITLE
  Minimal Valid Deck

DIMENS
  10 10 3 /

WELLDIMS
  2 10 1 2 /

GRID
DX
  300*100 /
DY
  300*100 /
DZ
  300*10 /

PROP
S
PVTW
  350  1.0  4.0E-5  0.5  0 /

SWOF
  0.2  0.0  1.0  0.0
  1.0  1.0  0.0  0.0
/

SOLUTION

SCHEDULE
TSTEP
  30 30 /

END
"""

EMPTY_DECK = ""

NO_SECTIONS_DECK = """
-- Just a comment
DIMENS
  10 10 3 /
"""

MISSING_END_DECK = """
RUNSPEC
DIMENS
  10 10 3 /
GRID
DX
  300*100 /
DY
  300*100 /
DZ
  300*10 /
PROPS
PVTW
  350  1.0  4.0E-5  0.5  0 /
SWOF
  0.2  0.0  1.0  0.0
  1.0  1.0  0.0  0.0
/
SOLUTION
SCHEDULE
TSTEP
  30 /
-- no END keyword
"""

BAD_DIMENS_DECK = """
RUNSPEC
DIMENS
  0 10 3 /
GRID
DX
  300*100 /
DY
  300*100 /
DZ
  300*10 /
PROPS
PVTW
  350  1.0  4.0E-5  0.5  0 /
SWOF
  0.2  0.0  1.0  0.0
  1.0  1.0  0.0  0.0
/
SOLUTION
SCHEDULE
TSTEP
  30 /
END
"""


# ── Tests ───────────────────────────────────────────────────────────────────

def test_lint_returns_lintresult():
    """lint_deck always returns a LintResult."""
    result = lint_deck(MINIMAL_VALID_DECK, use_llm=False)
    assert isinstance(result, LintResult)


def test_empty_deck_has_fatal_sections():
    """An empty deck must flag all 5 required sections as FATAL."""
    result = lint_deck(EMPTY_DECK, use_llm=False)
    fatal_keywords = {d.keyword for d in result.fatals}
    for section in ["RUNSPEC", "GRID", "PROPS", "SOLUTION", "SCHEDULE"]:
        assert section in fatal_keywords, f"{section} not flagged as fatal"


def test_missing_end_is_fatal():
    """Missing END keyword must produce a FATAL diagnostic."""
    result = lint_deck(MISSING_END_DECK, use_llm=False)
    rule_ids = {d.rule_id for d in result.fatals}
    assert "R002" in rule_ids, "R002 (missing END) not triggered"


def test_zero_dimens_is_fatal():
    """DIMENS with a zero value must be flagged as FATAL."""
    result = lint_deck(BAD_DIMENS_DECK, use_llm=False)
    dimens_fatals = [d for d in result.fatals if d.keyword == "DIMENS"]
    assert len(dimens_fatals) >= 1, "Zero DIMENS not flagged"


def test_no_sections_deck():
    """A deck with no sections should not be runnable."""
    result = lint_deck(NO_SECTIONS_DECK, use_llm=False)
    assert not result.is_runnable


def test_is_runnable_false_on_fatal():
    """is_runnable must be False when any FATAL diagnostic exists."""
    result = lint_deck(EMPTY_DECK, use_llm=False)
    assert result.is_runnable is False


def test_fallback_summary_no_llm():
    """Offline fallback summary must always be a non-empty string."""
    result = lint_deck(EMPTY_DECK, use_llm=False)
    assert isinstance(result.llm_summary, str)
    assert len(result.llm_summary) > 0


def test_helper_properties():
    """LintResult.errors / warnings / styles helpers work correctly."""
    result = lint_deck(MISSING_END_DECK, use_llm=False)
    # All diagnostics must be covered by severity properties
    total = len(result.fatals) + len(result.errors) + len(result.warnings) + len(result.styles)
    assert total == len(result.diagnostics)


def test_style_no_title():
    """Deck without TITLE keyword should produce a STYLE diagnostic."""
    result = lint_deck(MISSING_END_DECK, use_llm=False)
    style_ids = {d.rule_id for d in result.styles}
    assert "S001" in style_ids, "S001 (missing TITLE) not triggered"


def test_crash_report_integration():
    """CrashReports from runner are merged into LintResult diagnostics."""
    from opm_ai.runner.models import CrashReport
    reports = [
        CrashReport(severity="ERROR", message="Unknown keyword PORO2", keyword="PORO2"),
    ]
    result = lint_deck(MINIMAL_VALID_DECK, crash_reports=reports, use_llm=False)
    runner_diags = [d for d in result.diagnostics if d.rule_id == "RUNNER"]
    assert len(runner_diags) == 1
    assert runner_diags[0].keyword == "PORO2"
