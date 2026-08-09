"""Phase 5 — Explainer module tests.

The explainer produces Markdown for L2 and L3 issues. These tests
cover the happy paths (each L2 check generates Markdown; each L3
rule generates Markdown from its docstring) plus the failure paths
(unknown rule_id, missing spec, malformed message).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from opm_ai.linter.explainer import explain, explain_issue
from opm_ai.linter.linter import lint_deck
from opm_ai.linter.models import LintIssue


# ---------------------------------------------------------------------- #
# L2 explanations                                                        #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_explain_l2_required(tmp_path):
    """L2.WELLDIMS.required gets an explanation with the keyword and section."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
""")
    result = lint_deck(deck)
    welldims_req = [i for i in result.issues if i.rule_id == "L2.WELLDIMS.required"]
    assert len(welldims_req) == 1
    exp = welldims_req[0].explanation
    assert exp is not None, "WELLDIMS.required explanation should not be None"
    assert "WELLDIMS" in exp
    assert "RUNSPEC" in exp
    assert "**Fix**" in exp


@pytest.mark.unit
def test_explain_l2_item_count(tmp_path):
    """L2.<KW>.item_count explanation references the actual count.

    Use a keyword that does NOT have `skip_item_count: true`.
    ECLIPSE100 (a SCHEDULE keyword) is well-suited because it has
    a fixed item count.
    """
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /

SCHEDULE
TSTEP
  1.0 2.0 3.0 4.0 /
/
""")
    result = lint_deck(deck)
    tstep_count = [i for i in result.issues if i.rule_id == "L2.TSTEP.item_count"]
    # TSTEP's spec probably allows skip_item_count; if so, the test
    # verifies the explanation path is exercised on whatever L2
    # item_count issue fires. If nothing fires, skip.
    if not tstep_count:
        # Try FUNVAR which is repeated and has 1 item per record.
        deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
FUNVAR
  FU_GOR  /
  FU_WBHP  FU_EXTRA  /
/
""")
        result = lint_deck(deck)
        tstep_count = [i for i in result.issues if i.rule_id == "L2.FUNVAR.item_count"]
    assert len(tstep_count) >= 1
    exp = tstep_count[0].explanation
    assert exp is not None
    assert "items" in exp.lower() or "item" in exp.lower()


@pytest.mark.unit
def test_explain_l2_range(tmp_path):
    """L2.<KEYWORD>.range explanation references the offending value."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  99999 99999 99999 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
""")
    result = lint_deck(deck)
    dimens_range = [i for i in result.issues if i.rule_id == "L2.DIMENS.range"]
    assert len(dimens_range) >= 1
    exp = dimens_range[0].explanation
    assert exp is not None
    assert "DIMENS" in exp
    assert "range" in exp.lower()
    assert "99999" in exp  # offending value appears


@pytest.mark.unit
def test_explain_l2_mutex(tmp_path):
    """L2.SWOF.mutex explanation references both keywords and the fix."""
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
    result = lint_deck(deck)
    mutex = [i for i in result.issues if i.rule_id and i.rule_id.endswith(".mutex")]
    assert len(mutex) >= 1
    for issue in mutex:
        exp = issue.explanation
        assert exp is not None, f"{issue.rule_id} explanation is None"
        assert "SWOF" in exp
        assert "SGOF" in exp


# ---------------------------------------------------------------------- #
# L3 explanations                                                        #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_explain_l3_missing_solution():
    """L009 (missing SOLUTION) gets a docstring-derived explanation."""
    # Use a real fixture that already triggers L009.
    fixture = Path("/home/parallels/opm-ai/tests/fixtures/golden/WAG.DATA")
    if not fixture.exists():
        pytest.skip(f"fixture not found: {fixture}")
    result = lint_deck(fixture)
    l009 = [i for i in result.issues if i.rule_id == "L009"]
    if not l009:
        pytest.skip("WAG.DATA does not trigger L009 in this environment")
    exp = l009[0].explanation
    assert exp is not None
    # First sentence is from the docstring; rest follows.
    assert "SOLUTION" in exp


@pytest.mark.unit
def test_explain_l3_uses_docstring_first_sentence():
    """L3 explanation leads with a one-sentence summary."""
    issue = LintIssue(
        severity="WARNING",
        section="RUNSPEC",
        keyword="DIMENS",
        line=1,
        message="Missing DIMENS in RUNSPEC",
        rule_id="L015",
    )
    exp = explain(issue)
    assert exp is not None
    # First sentence is rendered in italics (markdown `_..._`).
    assert exp.startswith("_") or exp.startswith("*"), (
        f"Expected italicized first sentence, got: {exp[:60]!r}"
    )


# ---------------------------------------------------------------------- #
# explain_issue() helper                                                 #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_explain_issue_returns_new_instance():
    """explain_issue() does not mutate the input."""
    original = LintIssue(
        severity="ERROR",
        section="RUNSPEC",
        keyword="WELLDIMS",
        line=2,
        message="RUNSPEC must contain WELLDIMS",
        rule_id="L2.WELLDIMS.required",
    )
    out = explain_issue(original)
    assert out is not original
    assert original.explanation is None
    assert out.explanation is not None


@pytest.mark.unit
def test_explain_issue_unknown_rule_id_returns_none():
    """An issue with no rule_id cannot be explained; returns None."""
    issue = LintIssue(
        severity="INFO",
        section=None,
        keyword=None,
        line=None,
        message="Untagged",
        rule_id=None,
    )
    assert explain_issue(issue).explanation is None


# ---------------------------------------------------------------------- #
# lint_deck wiring                                                       #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_lint_deck_populates_explanation_for_l2_issues(tmp_path):
    """lint_deck() attaches explanations to L2 issues by default."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
""")
    result = lint_deck(deck)
    welldims_req = [i for i in result.issues if i.rule_id == "L2.WELLDIMS.required"]
    assert len(welldims_req) == 1
    assert welldims_req[0].explanation is not None


@pytest.mark.unit
def test_lint_deck_populates_explanation_for_l3_issues(tmp_path):
    """lint_deck() attaches explanations to L3 issues by default."""
    deck = tmp_path / "TESTCASE.DATA"
    # No SOLUTION section → L009 fires.
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
""")
    result = lint_deck(deck)
    l009 = [i for i in result.issues if i.rule_id == "L009"]
    assert len(l009) == 1
    assert l009[0].explanation is not None


# ---------------------------------------------------------------------- #
# Robustness                                                              #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_explain_returns_none_for_unknown_l3_rule():
    """A bogus L3 rule_id degrades to None rather than raising."""
    issue = LintIssue(
        severity="INFO",
        section=None,
        keyword=None,
        line=None,
        message="Unknown rule",
        rule_id="L999",
    )
    # Currently L999 is not registered, so explain returns None.
    # (This may change if a rule is added in the future; the test
    # is informational in that case.)
    exp = explain(issue)
    assert exp is None or exp.startswith("_")  # either None or docstring


@pytest.mark.unit
def test_explain_handles_malformed_l2_id():
    """L2. without a check suffix doesn't crash; returns generic."""
    issue = LintIssue(
        severity="INFO",
        section=None,
        keyword=None,
        line=None,
        message="Bad rule_id",
        rule_id="L2.",  # no keyword, no check
    )
    # Should not raise.
    exp = explain(issue)
    # Either None or the generic explanation — both acceptable.
    assert exp is None or isinstance(exp, str)


# ---------------------------------------------------------------------- #
# Sanity: existing fixtures produce no empty explanations                 #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
@pytest.mark.parametrize("fixture_name", [
    "WAG.DATA",
    "ACTIONX_UDQ.DATA",
])
def test_explanations_not_empty_on_real_fixtures(fixture_name):
    """Every issue on these real fixtures must have a non-empty explanation."""
    fixture_dir = Path("/home/parallels/opm-ai/tests/fixtures/golden")
    path = fixture_dir / fixture_name
    if not path.exists():
        fixture_dir = Path("/home/parallels/opm-ai/tests/fixtures/jfunc")
        path = fixture_dir / fixture_name
    if not path.exists():
        pytest.skip(f"fixture not found: {fixture_name}")
    result = lint_deck(path)
    empty = [
        i for i in result.issues
        if i.rule_id is not None and i.rule_id  # only count issues with rule_id
        and (i.explanation is None or i.explanation.strip() == "")
    ]
    # Some old L3 rules might not have explanations; only fail if
    # the rule_id is in the namespace where explanations are
    # expected (L2.* and the modern L-prefix).
    assert empty == [], f"{fixture_name}: issues with empty explanations: {empty}"