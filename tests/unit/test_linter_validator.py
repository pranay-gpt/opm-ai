"""Phase 3 — schema-driven L2 validator tests.

These tests exercise the L2 layer (`opm_ai.linter.validator`) end-to-end
through `lint_deck`. The validator emits issues with rule_id in the
`L2.<KEYWORD>.<CHECK>` namespace so downstream consumers can filter.

Tests are isolated to fixture decks built in `tmp_path` so they do
not depend on the SPE1/Norne fixtures. The phase-3 calibration
invariant (SPE1/SPE3/SPE9/Norne regression) is enforced separately
in `tests/integration/test_dataset_validation.py`.
"""
from __future__ import annotations

import pytest

from opm_ai.linter.linter import lint_deck


# ---------------------------------------------------------------------- #
# Required check (L2.<KEYWORD>.required)                                 #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_l2_welldims_required_missing(tmp_path):
    """L2.WELLDIMS.required fires when WELLDIMS absent from RUNSPEC."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10 10 3 /
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.WELLDIMS.required"
    ]
    assert len(matches) == 1, f"expected 1 L2.WELLDIMS.required, got {matches}"
    assert matches[0].severity == "ERROR"
    assert matches[0].section == "RUNSPEC"
    assert matches[0].keyword == "WELLDIMS"


@pytest.mark.unit
def test_l2_welldims_required_present(tmp_path):
    """No L2.WELLDIMS.required when WELLDIMS is present."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10 10 3 /
WELLDIMS
  5  2  1  9  0  0  0  0  0  0  0  0 /
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.WELLDIMS.required"
    ]
    assert matches == []


@pytest.mark.unit
def test_l2_welldims_skipped_when_section_includes(tmp_path):
    """L2.WELLDIMS.required does NOT fire if RUNSPEC has INCLUDE.

    The keyword may live in an included file, which the v1 linter does
    not resolve.
    """
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
INCLUDE
  'welldims.inc' /
DIMENS
  10 10 3 /
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.WELLDIMS.required"
    ]
    assert matches == [], f"unexpected L2.WELLDIMS.required: {matches}"


# ---------------------------------------------------------------------- #
# Item-count check (L2.<KEYWORD>.item_count)                            #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_l2_welldims_item_count_accepts_prefix(tmp_path):
    """WELLDIMS with 4 items passes (items 5-12 default to 0)."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10 10 3 /
WELLDIMS
  5  2  1  9 /
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.WELLDIMS.item_count"
    ]
    assert matches == [], f"unexpected item_count: {matches}"


@pytest.mark.unit
def test_l2_welldims_item_count_too_many(tmp_path):
    """WELLDIMS with 13+ items triggers L2.WELLDIMS.item_count ERROR."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10 10 3 /
WELLDIMS
  1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 /
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.WELLDIMS.item_count"
    ]
    assert len(matches) == 1, f"expected 1 item_count, got {matches}"
    assert matches[0].severity == "WARNING"  # calibrated: WARNING
    assert "exceeds" in matches[0].message or "more" in matches[0].message


@pytest.mark.unit
def test_l2_dimens_exactly_3_items(tmp_path):
    """DIMENS accepts only exactly 3 items (no defaults)."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10  10  3 /
WELLDIMS
  5  2  1  9  0  0  0  0  0  0  0  0 /
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.DIMENS.item_count"
    ]
    assert matches == [], f"unexpected DIMENS item_count: {matches}"


@pytest.mark.unit
def test_l2_dimens_wrong_count_fires(tmp_path):
    """DIMENS with 2 items triggers L2.DIMENS.item_count ERROR."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10  10  /
WELLDIMS
  5  2  1  9  0  0  0  0  0  0  0  0 /
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.DIMENS.item_count"
    ]
    assert len(matches) == 1, f"expected 1 DIMENS item_count, got {matches}"
    assert matches[0].severity == "INFO"  # DIMENS not yet calibrated


# ---------------------------------------------------------------------- #
# Item-range check (L2.<KEYWORD>.range)                                  #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_l2_welldims_item_range_out_of_bounds(tmp_path):
    """max_wells=999999 exceeds spec range [0, 100000] -> ERROR."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10 10 3 /
WELLDIMS
  999999  2  1  9  0  0  0  0  0  0  0  0 /
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.WELLDIMS.range"
    ]
    assert len(matches) == 1, f"expected 1 range issue, got {matches}"
    assert matches[0].severity == "WARNING"  # calibrated: WARNING
    assert "max_wells" in matches[0].message


@pytest.mark.unit
def test_l2_welldims_item_range_in_bounds(tmp_path):
    """Valid range values do not fire."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10 10 3 /
WELLDIMS
  500  50  10  100  0  0  0  0  0  0  0  0 /
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.WELLDIMS.range"
    ]
    assert matches == [], f"unexpected range issues: {matches}"


# ---------------------------------------------------------------------- #
# Coexistence with L1/L3 layer                                           #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_l015_and_l2_dimens_both_fire_during_coexistence(tmp_path):
    """During Phase 3 coexistence, L015 (L3) and L2.DIMENS.required
    (L2) both fire when DIMENS is missing.

    This test is the *proof* that the L2 layer runs in addition to
    the existing L3 layer, not instead of it. Migration happens in
    Phase 3 commit-2 (separate commit on this branch).
    """
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
WELLDIMS
  5  2  1  9  0  0  0  0  0  0  0  0 /
""")
    issues = lint_deck(deck).issues
    rule_ids = {i.rule_id for i in issues if i.rule_id}
    assert "L015" in rule_ids, f"L015 missing from issues: {rule_ids}"
    assert "L2.DIMENS.required" in rule_ids, (
        f"L2.DIMENS.required missing: {rule_ids}"
    )


@pytest.mark.unit
def test_no_false_positive_on_well_formed_deck(tmp_path):
    """A deck with valid WELLDIMS + DIMENS produces no L2 issues
    for those keywords. (Other L2 issues from other specs may fire
    on this minimal deck; we only check the WELLDIMS/DIMENS subset.)
    """
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10 10 3 /
WELLDIMS
  5  2  1  9  0  0  0  0  0  0  0  0 /
""")
    issues = lint_deck(deck).issues
    welldims_l2 = [
        i for i in issues
        if i.rule_id and i.rule_id.startswith("L2.WELLDIMS")
    ]
    dimens_l2 = [
        i for i in issues
        if i.rule_id and i.rule_id.startswith("L2.DIMENS")
    ]
    assert welldims_l2 == [], f"unexpected L2.WELLDIMS issues: {welldims_l2}"
    assert dimens_l2 == [], f"unexpected L2.DIMENS issues: {dimens_l2}"
