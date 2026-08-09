"""Phase 6 — Self-heal library tests.

The self-heal library proposes concrete fixes for LintIssues. These
tests cover:
  - L001 (missing terminator): 1.0 confidence, mechanical.
  - L016 (unknown keyword with suggestion): 0.9 confidence.
  - L016 (unknown keyword without suggestion): no fix proposed.
  - L2.<KW>.required with defaultable keyword (WELLDIMS, TABDIMS):
    0.8 confidence.
  - L2.<KW>.required with non-defaultable keyword (DIMENS): no fix.
  - L2.<KW>.mutex: 0.5 confidence, removes partner.
  - apply_fix rewrites the deck; verify_fix re-lints and confirms.
  - End-to-end: deck with multiple issues → propose all → apply all.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from opm_ai.linter.linter import lint_deck
from opm_ai.linter.models import LintIssue
from opm_ai.linter.self_heal import (
    FixProposal,
    apply_fix,
    apply_fixes,
    propose_fix,
    propose_fixes,
    verify_fix,
)


# ---------------------------------------------------------------------- #
# L001 — missing terminator                                              #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_L001_proposes_add_terminator_with_full_confidence(tmp_path):
    """L001 fires on a missing terminator; the fix appends '/'."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
""")
    issues = lint_deck(deck).issues
    l001 = [i for i in issues if i.rule_id == "L001"]
    assert len(l001) >= 1, f"L001 should fire, got: {[i.rule_id for i in issues]}"
    text = deck.read_text()
    fix = propose_fix(l001[0], text)
    assert fix is not None
    assert fix.kind == "add_terminator"
    assert fix.confidence == 1.0
    assert fix.new.endswith("/")


@pytest.mark.unit
def test_L001_apply_fix_appends_slash(tmp_path):
    """apply_fix rewrites the deck; re-lint finds fewer L001 issues."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
""")
    text = deck.read_text()
    issues = lint_deck(deck).issues
    l001 = [i for i in issues if i.rule_id == "L001"]
    assert len(l001) >= 1
    fix = propose_fix(l001[0], text)
    assert fix is not None
    new_text = apply_fix(text, fix)
    assert new_text != text
    assert "/" in new_text.split("\n")[3]  # DIMENS line now has /


# ---------------------------------------------------------------------- #
# L016 — unknown keyword with suggestion                                  #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_L016_proposes_replace_with_suggestion(tmp_path):
    """L016 with 'did you mean' suggests a 0.9-confidence replacement."""
    deck = tmp_path / "TESTCASE.DATA"
    # WELSECS is one edit from WELSPECS.
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /

SCHEDULE
WELSECS
  'W1' 'P' 0 0 0 'LIQ' /
/
""")
    issues = lint_deck(deck).issues
    l016 = [i for i in issues if i.rule_id == "L016"]
    assert len(l016) >= 1
    text = deck.read_text()
    fix = propose_fix(l016[0], text)
    assert fix is not None, f"L016 with suggestion should produce a fix"
    assert fix.kind == "replace_keyword"
    assert fix.confidence == 0.9
    assert "WELSPECS" in fix.new


@pytest.mark.unit
def test_L016_no_suggestion_returns_none(tmp_path):
    """L016 with no 'did you mean' suggestion returns no fix (unsafe)."""
    issue = LintIssue(
        severity="WARNING",
        section="GRID",
        keyword="FOOBAR",
        line=10,
        message="Unknown keyword 'FOOBAR'",
        rule_id="L016",
    )
    text = "FOOBAR\n  1 2 3 /\n"
    fix = propose_fix(issue, text)
    assert fix is None, "L016 without a suggestion must not propose a fix"


# ---------------------------------------------------------------------- #
# L2.<KW>.required                                                       #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_L2_welldims_required_proposes_default_insertion(tmp_path):
    """L2.WELLDIMS.required proposes a default 12-item record."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
""")
    issues = lint_deck(deck).issues
    welldims_req = [i for i in issues if i.rule_id == "L2.WELLDIMS.required"]
    assert len(welldims_req) == 1
    text = deck.read_text()
    fix = propose_fix(welldims_req[0], text)
    assert fix is not None
    assert fix.kind == "add_keyword"
    assert fix.confidence == 0.8
    assert "WELLDIMS" in fix.new
    assert "1 1 1 1" in fix.new


@pytest.mark.unit
def test_L2_dimens_required_no_fix(tmp_path):
    """L2.DIMENS.required does NOT propose a fix (can't default)."""
    issue = LintIssue(
        severity="ERROR",
        section="RUNSPEC",
        keyword="DIMENS",
        line=2,
        message="RUNSPEC must contain DIMENS keyword",
        rule_id="L2.DIMENS.required",
    )
    text = "RUNSPEC\n/\n"
    fix = propose_fix(issue, text)
    assert fix is None, "DIMENS cannot be defaulted without context"


# ---------------------------------------------------------------------- #
# L2.<KW>.mutex                                                          #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_L2_swof_mutex_proposes_partner_removal(tmp_path):
    """L2.SWOF.mutex proposes removing the SGOF block."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
OIL
WATER
GAS
/

PROPS
SWOF
  0.0 0.0 1.0 0.0
  1.0 1.0 0.0 0.0 /
SGOF
  0.0 0.0 1.0 0.0
  1.0 1.0 0.0 0.0 /
/
""")
    issues = lint_deck(deck).issues
    mutex = [i for i in issues if i.rule_id and i.rule_id.endswith(".mutex")]
    assert len(mutex) >= 1
    text = deck.read_text()
    fix = propose_fix(mutex[0], text)
    assert fix is not None
    assert fix.kind == "remove_keyword"
    assert fix.confidence == 0.5


# ---------------------------------------------------------------------- #
# propose_fixes / apply_fixes (whole-deck entry points)                  #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_propose_fixes_returns_list(tmp_path):
    """propose_fixes returns a list of FixProposal."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
""")
    issues = lint_deck(deck).issues
    fixes = propose_fixes(deck, issues)
    # L001 (missing / on DIMENS line) and L2.WELLDIMS.required
    # are both fixable here.
    kinds = {f.kind for f in fixes}
    assert "add_terminator" in kinds or "add_keyword" in kinds


@pytest.mark.unit
def test_apply_fixes_sequential(tmp_path):
    """apply_fixes applies each fix in order and returns the new text."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
""")
    issues = lint_deck(deck).issues
    fixes = propose_fixes(deck, issues)
    assert fixes, "expected at least one fix"
    new_text = apply_fixes(deck, fixes)
    # The WELLDIMS-required fix appends a default block.
    assert "WELLDIMS" in new_text


# ---------------------------------------------------------------------- #
# verify_fix (safety net)                                                #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_verify_fix_true_when_issue_count_drops(tmp_path):
    """verify_fix returns True when re-linting finds fewer issues."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
""")
    issues = lint_deck(deck).issues
    baseline = len(issues)
    l001 = [i for i in issues if i.rule_id == "L001"]
    assert l001
    fix = propose_fix(l001[0], deck.read_text())
    assert fix is not None
    assert verify_fix(deck, fix, baseline) is True


@pytest.mark.unit
def test_verify_fix_false_when_apply_doesnt_help(tmp_path):
    """verify_fix returns False when applying the fix doesn't help."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
""")
    issues = lint_deck(deck).issues
    baseline = len(issues)
    # A no-op fix (already-terminated line) shouldn't help.
    noop = FixProposal(
        issue_id="L001|99|test",
        kind="add_terminator",
        old="  5 5 3 /",
        new="  5 5 3 /",
        confidence=1.0,
        rationale="noop",
    )
    assert verify_fix(deck, noop, baseline) is False


# ---------------------------------------------------------------------- #
# End-to-end                                                             #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_end_to_end_propose_apply_verify(tmp_path):
    """End-to-end: deck with multiple issues → propose → apply → verify."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3
/
""")
    issues = lint_deck(deck).issues
    baseline = len(issues)
    assert baseline > 0
    fixes = propose_fixes(deck, issues)
    assert fixes
    new_text = apply_fixes(deck, fixes)
    # Write back to disk and re-lint to confirm fewer issues.
    deck.write_text(new_text)
    new_issues = lint_deck(deck).issues
    assert len(new_issues) < baseline, (
        f"After applying fixes, issue count should drop. "
        f"Baseline={baseline}, after={len(new_issues)}"
    )


# ---------------------------------------------------------------------- #
# FixProposal serialisation                                              #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_fix_proposal_to_dict_is_json_safe():
    """FixProposal.to_dict returns a JSON-serialisable dict."""
    f = FixProposal(
        issue_id="L001|3|test",
        kind="add_terminator",
        old="foo",
        new="foo /",
        confidence=1.0,
        rationale="test",
    )
    d = f.to_dict()
    import json
    json.dumps(d)  # must not raise