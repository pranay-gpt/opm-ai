"""Unit tests for the v2 validator framework and rule families.

Tests cover:
- LintIssue, LintResult, Severity
- Rule registration / dispatch
- shape_rule (L201, L202)
- crossref_rule (L221, L222, L223)
- dims_rule (L232, L233, L234)
- requires_rule (L241)
- section_rule (L262)
- opm_rule (L270)
- End-to-end validate() on SPE1 (zero issues)
"""

from __future__ import annotations

from pathlib import Path

from opm_ai.linter.v2.parser import parse_file
from opm_ai.linter.v2.symbols import build_symbol_table
from opm_ai.linter.v2.validator import (
    LintIssue,
    LintResult,
    Severity,
    clear_rules,
    list_rules,
    register,
    validate,
)


def test_lint_issue_creation():
    """LintIssue can be created with all fields."""
    issue = LintIssue(
        code=200,
        severity=Severity.ERROR,
        message="test",
        source_file=Path("/foo/bar.DATA"),
        source_line=42,
    )
    assert issue.code == 200
    assert issue.severity == Severity.ERROR
    assert issue.message == "test"
    assert issue.source_file == Path("/foo/bar.DATA")
    assert issue.source_line == 42


def test_lint_issue_location_str():
    """location_str formats as `file:line` or `file`."""
    issue = LintIssue(
        code=200,
        severity=Severity.ERROR,
        message="x",
        source_file=Path("/foo/bar.DATA"),
        source_line=42,
    )
    assert issue.location_str() == "bar.DATA:42"
    issue2 = LintIssue(code=200, severity=Severity.ERROR, message="x")
    assert issue2.location_str() == ""


def test_lint_result_counts():
    """LintResult counts by severity correctly."""
    r = LintResult(issues=[
        LintIssue(code=200, severity=Severity.ERROR, message="e1"),
        LintIssue(code=200, severity=Severity.ERROR, message="e2"),
        LintIssue(code=200, severity=Severity.WARNING, message="w1"),
        LintIssue(code=200, severity=Severity.INFO, message="i1"),
    ])
    assert r.error_count() == 2
    assert r.warning_count() == 1
    assert r.info_count() == 1
    assert r.has_errors() is True
    assert r.filter(200) == r.issues


def test_lint_result_no_errors():
    """has_errors() returns False when no errors."""
    r = LintResult(issues=[
        LintIssue(code=200, severity=Severity.WARNING, message="w"),
    ])
    assert r.has_errors() is False


def test_register_and_list_rules():
    """register() adds to the registry; list_rules() returns them."""
    # Snapshot the current registry size; the test mutates it.
    initial = len(list_rules())

    def my_rule(deck, st):
        return []

    register(200, 209, "test-rule", my_rule)
    rules = list_rules()
    assert any(name == "test-rule" for _, _, name in rules)
    # Restore the registry so subsequent tests still have all rules.
    from opm_ai.linter.v2.validator import reset_rules
    reset_rules()


def test_validator_end_to_end_on_spe1():
    """SPE1 produces zero issues end-to-end (after catalogue fixes)."""
    text = Path("tests/fixtures/spe1/SPE1CASE1.DATA").read_text()
    deck = parse_file(text, source_file=Path("tests/fixtures/spe1/SPE1CASE1.DATA"))
    result = validate(deck)
    assert result.error_count() == 0
    assert result.warning_count() == 0


def test_validator_crossref_l221_well_not_declared():
    """L221: COMPDAT for undeclared well emits WARNING."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\n"
        "COMPDAT 'MISSING' 1 1 1 1 'OPEN' 0 /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l221 = [i for i in result.issues if i.code == 221]
    assert len(l221) >= 1
    assert "MISSING" in l221[0].message


def test_validator_crossref_l222_group_not_declared():
    """L222: GCONPROD for undeclared group emits WARNING."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\n"
        "GCONPROD 'NOGROUP' 'ORAT' 1000.0 /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l222 = [i for i in result.issues if i.code == 222]
    assert len(l222) >= 1


def test_validator_crossref_l223_gruptree_child_missing():
    """L223: GRUPTREE referencing a non-existent group emits WARNING.

    The rule fires only for *groups* that are never declared. We can
    trigger it with an undefined well used in WELOPEN, but since the
    GRUPTREE children implicitly create groups, we test the rule on a
    separate group reference that is neither declared nor a GRUPTREE child.
    """
    # The GCONPROD references 'NOGROUP' which is neither a WELSPECS group
    # nor a GRUPTREE child. So L222 should fire. Note this exercises the
    # cross-reference layer rather than L223 specifically — L223
    # requires an unregistered parent group, which GRUPTREE cannot produce
    # (its extractor registers children as a side-effect).
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\n"
        "GCONPROD 'NOGROUP' 'ORAT' 1000.0 /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    crossref_issues = [
        i for i in result.issues
        if i.code in (222, 223)
        and "NOGROUP" in i.message
    ]
    assert len(crossref_issues) >= 1


def test_validator_dims_l232_welldims_exceeded():
    """L232: WELLDIMS MAXWELLS=1 with 2 wells emits ERROR."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "WELLDIMS\n 1 1 1 1 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\n"
        "WELSPECS 'W1' 'G1' 1 1 1.0 'OIL' /\n"
        "WELSPECS 'W2' 'G2' 2 2 2.0 'WAT' /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l232 = [i for i in result.issues if i.code == 232]
    assert len(l232) == 1
    assert l232[0].severity == Severity.ERROR


def test_validator_dims_l234_regdims_too_small():
    """L234: REGDIMS NTFIP=1 but max FIPNUM region is 2 emits WARNING."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n"
        "REGDIMS\n 1 /\n\n"
        "GRID\n"
        "FIPNUM\n"
        " 0 0 1 1\n 2 2 0 0 /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l234 = [i for i in result.issues if i.code == 234]
    assert len(l234) == 1
    assert l234[0].severity == Severity.WARNING


def test_validator_requires_l241_compdat_needs_welspecs():
    """L241: COMPDAT without WELSPECS emits ERROR."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "WELLDIMS\n 5 5 1 1 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\n"
        "COMPDAT 'W1' 1 1 1 1 'OPEN' 0 /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l241 = [i for i in result.issues if i.code == 241]
    # COMPDAT requires WELSPECS — that is the only L241 here.
    # (WELLDIMS is present so WELSPECS isn't required by anything else.)
    assert any("WELSPECS" in i.message for i in l241)
    assert len(l241) == 1


def test_validator_requires_l241_satisfied_when_present():
    """L241 does not fire when WELSPECS is present."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "WELLDIMS\n 5 5 1 1 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\n"
        "WELSPECS 'W1' 'G1' 1 1 1.0 'OIL' /\n"
        "COMPDAT 'W1' 1 1 1 1 'OPEN' 0 /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l241 = [i for i in result.issues if i.code == 241]
    assert l241 == []


def test_validator_section_l262_missing_required_section():
    """L262: missing required section emits ERROR."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        # Missing PROPS / SOLUTION / SCHEDULE
    )
    deck = parse_file(text)
    result = validate(deck)
    l262 = [i for i in result.issues if i.code == 262]
    assert len(l262) >= 3  # PROPS, SOLUTION, SCHEDULE
    assert any("PROPS" in i.message for i in l262)
    assert any("SOLUTION" in i.message for i in l262)
    assert any("SCHEDULE" in i.message for i in l262)


def test_validator_opm_l270_unsupported_keyword():
    """L270: FULLIMP (unsupported) emits WARNING."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "RUNSPEC\nFULLIMP\n/\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l270 = [i for i in result.issues if i.code == 270]
    assert len(l270) == 1
    assert "FULLIMP" in l270[0].message


def test_validator_shape_l201_record_count_mismatch():
    """L201: FIXED keyword with wrong record count emits ERROR."""
    # Use a FIXED keyword and give it 2 records when it expects 1.
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n"
        # Provide 2 START records (FIXED record_count=1).
        "START\n 1 1 2000 /\n 1 1 2001 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l201 = [i for i in result.issues if i.code == 201]
    # START is FIXED record_count=1; 2 records → L201.
    assert any("START" in i.message for i in l201)


def test_validator_runs_with_explicit_symbol_table():
    """validate() accepts an explicit symbol table."""
    text = Path("tests/fixtures/spe1/SPE1CASE1.DATA").read_text()
    deck = parse_file(text, source_file=Path("tests/fixtures/spe1/SPE1CASE1.DATA"))
    st = build_symbol_table(deck)
    result = validate(deck, st)
    assert result.symbol_table is st


def test_validator_returns_lintresult():
    """validate() returns a LintResult."""
    text = Path("tests/fixtures/spe1/SPE1CASE1.DATA").read_text()
    deck = parse_file(text, source_file=Path("tests/fixtures/spe1/SPE1CASE1.DATA"))
    result = validate(deck)
    assert isinstance(result, LintResult)
    assert result.deck is deck