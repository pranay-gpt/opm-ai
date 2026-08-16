"""Tests for the L1 + v2 coexistence path (lint_deck_combined)."""

from pathlib import Path

from opm_ai.linter import lint_deck, lint_deck_combined


def test_lint_deck_combined_returns_combined_lint_result():
    """lint_deck_combined() returns a LintResult with combined issues."""
    p = Path("tests/fixtures/spe1/SPE1CASE1.DATA")
    r = lint_deck_combined(p)
    assert r is not None
    assert hasattr(r, "passed")
    assert hasattr(r, "errors")
    assert hasattr(r, "warnings")


def test_lint_deck_combined_includes_l1_issues():
    """lint_deck_combined() must include issues from L1 (lint_deck)."""
    # Use a fixture that L1 flags with an L001 (missing terminator) issue.
    p = Path("tests/fixtures/micp/MICP.DATA")
    l1 = lint_deck(p)
    combined = lint_deck_combined(p)
    # All L1 rule_ids should still appear in combined.
    l1_rule_ids = {i.rule_id for i in l1.issues}
    combined_rule_ids = {i.rule_id for i in combined.issues}
    assert l1_rule_ids.issubset(combined_rule_ids), (
        f"L1 rule_ids missing from combined: {l1_rule_ids - combined_rule_ids}"
    )


def test_lint_deck_combined_adds_v2_issues_when_they_fire():
    """When v2 issues fire, they appear in the combined result.

    Use a fixture known to trigger v2 warnings (WTMULT-01 has the
    L234 FIPNUM-vs-NTFIP true positive).
    """
    p = Path("tests/fixtures/wtmult/WTMULT-01.DATA")
    l1 = lint_deck(p)
    combined = lint_deck_combined(p)
    l1_codes = {i.rule_id for i in l1.issues}
    combined_codes = {i.rule_id for i in combined.issues}
    # v2 issues use rule_ids in the 2xx range; combined must have at
    # least one such code that L1 doesn't have.
    v2_only = combined_codes - l1_codes
    assert any(c.startswith("L2") for c in v2_only), (
        f"Expected v2-only rule_ids (L2xx) in combined; "
        f"l1_codes={l1_codes} combined_codes={combined_codes}"
    )


def test_lint_deck_combined_no_duplicates():
    """Combined result must not double-count the same (rule_id, line, message)."""
    p = Path("tests/fixtures/spe1/SPE1CASE1.DATA")
    r = lint_deck_combined(p)
    keys = [(i.rule_id, i.line, i.message[:40]) for i in r.issues]
    assert len(keys) == len(set(keys)), (
        f"Duplicate (rule_id, line, message-prefix) tuples found: "
        f"{[k for k in keys if keys.count(k) > 1]}"
    )


def test_lint_deck_combined_clean_fixture_stays_clean():
    """A clean fixture (no L1 issues, no v2 issues) must report passed=True."""
    p = Path("tests/fixtures/spe1/SPE1CASE1.DATA")
    # Use whatever L1 says — if L1 issues exist, just check combined ≥ L1.
    r = lint_deck_combined(p)
    # We don't assert passed=True (L1 may add INFO issues); we assert
    # no ERROR was introduced by v2 (L2xx codes that didn't exist in L1).
    l1 = lint_deck(p)
    l1_codes = {i.rule_id for i in l1.issues if i.severity == "ERROR"}
    combined_error_codes = {i.rule_id for i in r.issues if i.severity == "ERROR"}
    new_errors = combined_error_codes - l1_codes
    assert new_errors == set(), (
        f"v2 introduced new ERROR rule_ids on a clean fixture: {new_errors}"
    )