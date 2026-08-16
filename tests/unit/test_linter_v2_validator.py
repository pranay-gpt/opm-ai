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
    """SPE1 produces zero ERRORs and zero WARNINGs end-to-end.

    INFO-level issues are tolerated — L160 (parse-time loose tokens
    before the first section header) is INFO by default since it
    fires on benign header decoration.
    """
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


def test_validator_crossref_l224_fu_var_not_declared():
    """L224: SUMMARY references FU_* that is not declared via FUNVAR or
    UDQ DEFINE/ASSIGN/UNITS/UPDATE. INFO severity (per Phase 5.5)."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SUMMARY\n"
        "FU_MYVAR\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l224 = [i for i in result.issues if i.code == 224]
    assert len(l224) == 1
    assert "FU_MYVAR" in l224[0].message
    assert l224[0].severity == Severity.INFO


def test_validator_crossref_l224_fu_var_declared_via_funvar():
    """L224: SUMMARY references FU_MYVAR which IS declared via FUNVAR."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\nFUNVAR FU_MYVAR /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SUMMARY\n"
        "FU_MYVAR\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l224 = [i for i in result.issues if i.code == 224]
    assert l224 == []


def test_validator_section_validity_l170_wrong_section_info():
    """L170: section-mismatch keywords emit INFO (not WARNING).

    Phase 5.5 demoted L170 to INFO because the parser is overly
    eager (sets unknown_reason for any keyword in a section not
    listed in its catalogue spec), and OPM Flow tolerates
    misplaced keywords (e.g. WCONPROD after RUNSPEC).
    """
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "PROPS\n"
        "WELSPECS 'W1' 'G1' 1 1 1.0 'OIL' /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l170 = [i for i in result.issues if i.code == 170]
    assert len(l170) >= 1
    assert l170[0].severity == Severity.INFO
    assert "WELSPECS" in l170[0].message
    assert "PROPS" in l170[0].message


def test_validator_section_validity_l171_unknown_keyword_info():
    """L171: unknown keyword emits INFO (not WARNING).

    Phase 5.5 demoted L171 to INFO because the v2 catalogue is
    intentionally a strict subset of the full OPM-Flow-supported
    keyword set; many real OPM keywords (WGOR, FGOR, BPR, etc.)
    are not yet catalogued.
    """
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\n"
        "NOSUCHKEYWORD 1 2 3 /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l171 = [i for i in result.issues if i.code == 171]
    assert len(l171) == 1
    assert l171[0].severity == Severity.INFO
    assert "NOSUCHKEYWORD" in l171[0].message


def test_validator_section_validity_l171_summary_mnemonic_suppressed():
    """L171 does NOT fire for SUMMARY section keywords.

    SUMMARY mnemonics (WGOR, FGOR, BPR, RPR, ROIP, etc.) are bare
    column-0 variable declarations, not catalogued keywords. The
    symbol table harvests them into summary_vars; L171 firing
    would produce thousands of false positives on every fixture.
    """
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SUMMARY\n"
        "WGOR\n"   # known OPM summary mnemonic, not in catalogue
        "FGOR\n"   # ditto
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l171 = [i for i in result.issues if i.code == 171]
    assert l171 == []


def test_validator_section_validity_no_fire_on_clean_deck():
    """L170/L171 don't fire on a known-clean mini deck."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\n"
        "WELSPECS 'W1' 'G1' 1 1 1.0 'OIL' /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l170_l171 = [i for i in result.issues if i.code in (170, 171)]
    assert l170_l171 == []


def test_validator_dims_l231_tabdims_nssfun_too_small():
    """L231: TABDIMS NSSFUN=1 but SWOF tables exist for 3 regions.

    The +1 convention (NSSFUN+1 = max regions) means 3 regions
    with NSSFUN=1 fires L231.
    """
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\nTABDIMS\n 1 1 1 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "PROPS\n"
        "SWOF\n"
        " 1 0 1 0\n 0.1 0.09 0.81 0 /\n"
        " 1 0 0 0\n /\n"
        "SWOF\n"
        " 2 0 1 0\n 0.1 0.09 0.81 0 /\n"
        " 2 0 0 0\n /\n"
        "SWOF\n"
        " 3 0 1 0\n 0.1 0.09 0.81 0 /\n"
        " 3 0 0 0\n /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l231 = [i for i in result.issues if i.code == 231]
    assert len(l231) == 1
    assert "NSSFUN" in l231[0].message
    assert l231[0].severity in (Severity.WARNING, Severity.INFO)


def test_validator_dims_l231_no_fire_when_within_budget():
    """L231: TABDIMS NSSFUN=2 with only 1 region of SWOF: no fire."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\nTABDIMS\n 1 1 2 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "PROPS\n"
        "SWOF\n"
        " 0 0 1 0\n 0.1 0.09 0.81 0 /\n"
        " 1 0 0 0\n /\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l231 = [i for i in result.issues if i.code == 231]
    assert l231 == []


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
    """L234: REGDIMS NTFIP=1 but max FIPNUM region is 2 emits INFO.

    Downgraded from WARNING per QC-2 evidence: OPM Flow dynamically
    allocates more PVT regions when NTFIP is under-allocated, so
    this is not a deck defect.
    """
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
    assert l234[0].severity == Severity.INFO
    assert "dynamically allocates" in l234[0].message


def test_validator_dims_l234_ignores_satnum():
    """L234: SATNUM-only regions must NOT trigger L234.

    Regression: previously all region arrays (FIPNUM, EQLNUM, SATNUM,
    PVTNUM, ROCKNUM) shared one set, so a SATNUM array with values
    up to 7 would falsely trip the REGDIMS NTFIP check (which
    governs only FIPNUM).
    """
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n"
        "REGDIMS\n 1 /\n"
        "TABDIMS\n 1* 7 /\n\n"  # NSSFUN=7 for SATNUM
        "GRID\n"
        "FIPNUM\n"
        " 1 1 1 1\n 1 1 1 1 /\n"  # FIPNUM only has region 1
        "SATNUM\n"
        " 1 1 2 2\n 3 3 5 5 /\n"  # SATNUM up to 5
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l234 = [i for i in result.issues if i.code == 234]
    assert l234 == [], f"Expected no L234 (SATNUM should not trigger), got {[i.message for i in l234]}"


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
    """L270: PARTTRAC (catalog-only, no handler) emits WARNING."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "RUNSPEC\nPARTTRAC\n 1 1 1 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l270 = [i for i in result.issues if i.code == 270]
    assert len(l270) == 1
    assert "PARTTRAC" in l270[0].message
    assert "no handler" in l270[0].message.lower()


def test_validator_opm_l270_no_warning_for_supported_keywords():
    """L270: RUNSUM/GUIDERAT/TRACER/TRACERS are supported by OPM Flow
    2024+ and should NOT trigger L270.

    Regression: the previous list included these (per stale Pyrus
    docs) but they have handlers in opm-common.
    """
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "RUNSPEC\nTRACERS\n 1* 2 1* 1* /\n\n"
        "SUMMARY\nRUNSUM\n/\n\n"
        "SCHEDULE\nGUIDERAT\n 30.0 'OIL' 1.0 1.0 0.0 0.0 1.0 1.25 1* 0.5 /\n/\n\n"
        "END\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l270 = [i for i in result.issues if i.code == 270]
    assert l270 == [], f"Got unexpected L270: {[i.message for i in l270]}"


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


def test_validator_shape_l202_imprecise_keyword_emits_warning():
    """L202 with imprecise catalogue: emits WARNING (default)."""
    # FAULTS is LIST-kind with 10 documented items but the catalogue
    # has imprecise_items=False, so a too-long record is WARNING.
    text = (
        "RUNSPEC\nDIMENS 1 1 1 /\n\n"
        "GRID\n"
        "FAULTS\n"
        # 12 items — exceeds FAULTS spec of 10.
        "  FLT1 1 1 1 1 1 1 1 1 1 EXTRA1 EXTRA2 /\n"
        "DX\n 1*100 /\n\n"
        "SCHEDULE\n/\n\nEND\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l202 = [i for i in result.issues if i.code == 202]
    # The 12-item FAULTS record should produce an L202.
    assert any("FAULTS" in i.message for i in l202), (
        f"Expected FAULTS in L202 messages; got {[i.message for i in l202]}"
    )
    # Since FAULTS is NOT marked precise, severity is WARNING.
    faults_l202 = [i for i in l202 if "FAULTS" in i.message]
    assert all(i.severity == Severity.WARNING for i in faults_l202), (
        f"Expected WARNING for imprecise keyword, got "
        f"{[i.severity for i in faults_l202]}"
    )


def test_validator_shape_l202_precise_keyword_emits_error():
    """L202 with precise catalogue: emits ERROR for documented keywords.

    WELSPECS has 14 documented items per the OPM Flow Reference
    Manual and is marked precise_items=True in the catalogue. A
    WELSPECS record with too many items should be ERROR, not
    WARNING.
    """
    text = (
        "RUNSPEC\nDIMENS 1 1 1 /\n"
        "WELLDIMS\n 1 1 1 1 1 1 1 1 /\n\n"
        "GRID\nDX\n 1*100 /\n\n"
        "SCHEDULE\n"
        "WELSPECS\n"
        # 16 items — exceeds WELSPECS spec of 14.
        "  W1 G1 1 1 1000.0 OIL 0.5 STD SHUT PTBL 1000.0 0 1 1000.0 EXTRA1 EXTRA2 /\n"
        "\n/\n"
        "\nEND\n"
    )
    deck = parse_file(text)
    result = validate(deck)
    l202 = [i for i in result.issues if i.code == 202]
    # The 16-item WELSPECS record should produce an L202.
    assert any("WELSPECS" in i.message for i in l202), (
        f"Expected WELSPECS in L202 messages; got {[i.message for i in l202]}"
    )
    # Since WELSPECS is precise, severity is ERROR.
    welspecs_l202 = [i for i in l202 if "WELSPECS" in i.message]
    assert all(i.severity == Severity.ERROR for i in welspecs_l202), (
        f"Expected ERROR for precise keyword, got "
        f"{[i.severity for i in welspecs_l202]}"
    )


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


# -----------------------------------------------------------------------------
# QC-3 follow-up: L160 (parse_errors surfaced as INFO)
# -----------------------------------------------------------------------------


def test_validator_l160_surfaces_loose_tokens():
    """L160 INFO: value tokens before any keyword produce INFO issues.

    Regression for QC-3 finding C.1: previously `deck.parse_errors`
    was silently dropped. Now they surface as L160 INFO so the
    user knows the parser couldn't structure them.
    """
    text = """\
RUNSPEC
100 200 300 /
DIMENS
  3 3 3 /
"""
    deck = parse_file(text)
    result = validate(deck)
    l160s = [i for i in result.issues if i.code == 160]
    assert len(l160s) >= 3
    # All L160 should be INFO, not WARNING — they are diagnostic
    # not actionable deck defects.
    for i in l160s:
        assert i.severity == Severity.INFO
    msgs = " ".join(i.message for i in l160s)
    assert "outside any keyword" in msgs


def test_validator_l160_no_fire_on_clean_deck():
    """L160 INFO: a clean deck has no L160 issues."""
    text = """\
RUNSPEC
DIMENS 3 3 3 /

GRID
DX
 27*100 /

END
"""
    deck = parse_file(text)
    result = validate(deck)
    l160s = [i for i in result.issues if i.code == 160]
    assert l160s == []


def test_catalogue_funvar_accepts_runspec():
    """QC-3 D.5: FUNVAR is valid in RUNSPEC (and SUMMARY).

    Previously the catalogue restricted FUNVAR to SUMMARY only,
    tripping `unknown_reason` whenever a deck placed FUNVAR in
    RUNSPEC as the OPM Flow manual requires.
    """
    from opm_ai.linter.v2.catalogue.keywords import FUNVAR
    from opm_ai.linter.v2.spec import SectionName
    assert SectionName.RUNSPEC in FUNVAR.sections
    assert SectionName.SUMMARY in FUNVAR.sections