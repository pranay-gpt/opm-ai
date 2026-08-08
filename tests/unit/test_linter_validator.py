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
    assert matches[0].severity == "WARNING"  # DIMENS calibrated in Phase 2.5


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


# ---------------------------------------------------------------------- #
# Phase 3.5: per-record validation                                       #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_l2_per_record_item_count_validates_every_record(tmp_path):
    """FUNVAR record 2 has 2 items → triggers L2.FUNVAR.item_count.

    Phase 3.5: previously only the first record was checked. Now every
    record gets validated. FUNVAR's spec has 1 item, so record 2 with
    2 items must fire. Record 1 with 1 item is OK.

    Per the OPM Flow manual, FUNVAR has 1 item (the variable name).
    The value of the FUNVAR (e.g. 1.0) is set via UDQ ASSIGN, not
    via FUNVAR itself.
    """
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  10 10 5 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
FUNVAR
  FU_GOR  /
  FU_WBHP  FU_EXTRA  /
/
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.FUNVAR.item_count"
    ]
    # Only record 2 (FU_WBHP) has 2 items; record 1 has 1 (correct).
    assert len(matches) == 1, f"expected 1 record 2 mismatch, got {matches}"
    assert "record 2" in matches[0].message


@pytest.mark.unit
def test_l2_per_record_item_range_validates_every_record(tmp_path):
    """PVTO with bad Bo in record 2 triggers L2.PVTO.range.

    Phase 3.5: range check iterates over every record. PVTO's Bo
    range is [1.0, 5.0] strict_min=True. Record 1 has Bo=1.1 (OK),
    record 2 has Bo=0.5 (below strict_min).
    """
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
OIL
/

PROPS
PVTO
  1000 14.7 1.1 1.0 /
  2000 19.7 0.5 1.0 /
/
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.PVTO.range"
    ]
    assert len(matches) == 1, f"expected 1 record-2 range mismatch, got {matches}"
    assert "record 2" in matches[0].message
    assert "below" in matches[0].message


# ---------------------------------------------------------------------- #
# Phase 3.5: mutex enforcement                                           #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_l2_mutex_coord_with_dx_fires(tmp_path):
    """Both COORD and DX in the GRID section fire L2.COORD.mutex."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /

GRID
DX
  75*1.0 /
COORD
  1 0 0
  1 1 0
  1 1 1 /
/
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.COORD.mutex"
    ]
    assert len(matches) >= 1, f"expected L2.COORD.mutex, got {[i.rule_id for i in issues]}"


@pytest.mark.unit
def test_l2_mutex_pvto_pvdo_fires(tmp_path):
    """Both PVTO and PVDO in PROPS fire L2.PVTO.mutex."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
OIL
/

PROPS
PVTO
  1000 14.7 1.1 1.0 /
PVDO
  14.7 1.1 1.0
  19.7 1.2 1.1 /
/
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.PVTO.mutex"
    ]
    assert len(matches) >= 1, f"expected L2.PVTO.mutex, got {[i.rule_id for i in issues]}"


@pytest.mark.unit
def test_l2_mutex_swof_sgof_soft_warning(tmp_path):
    """SWOF and SGOF co-occurring fires L2.SWOF.mutex as a soft warning."""
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
  0.2 0.0 0.8 0.0
  1.0 1.0 0.0 0.0 /
SGOF
  0.0 0.0 1.0 0.0
  0.2 0.0 0.8 0.0
  1.0 1.0 0.0 0.0 /
/
""")
    issues = lint_deck(deck).issues
    mutex = [
        i for i in issues
        if i.rule_id and i.rule_id.endswith(".mutex")
    ]
    # Both SWOF and SGOF fire (one each direction).
    swoff_mutex = [i for i in mutex if i.rule_id == "L2.SWOF.mutex"]
    sgof_mutex = [i for i in mutex if i.rule_id == "L2.SGOF.mutex"]
    assert len(swoff_mutex) == 1, f"expected 1 SWOF.mutex, got {swoff_mutex}"
    assert len(sgof_mutex) == 1, f"expected 1 SGOF.mutex, got {sgof_mutex}"


@pytest.mark.unit
def test_l2_mutex_no_false_positive_when_only_one_present(tmp_path):
    """Plain SWOF (no SGOF) does NOT fire L2.SWOF.mutex."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
OIL
WATER
/

PROPS
SWOF
  0.0 0.0 1.0 0.0
  0.2 0.0 0.8 0.0
  1.0 1.0 0.0 0.0 /
/
""")
    issues = lint_deck(deck).issues
    mutex = [
        i for i in issues
        if i.rule_id and i.rule_id.endswith(".mutex")
    ]
    assert mutex == [], f"unexpected mutex issues: {mutex}"


# ---------------------------------------------------------------------- #
# Phase 3.5: ENDSCALE schema fix                                         #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_l2_endscale_with_strings_passes(tmp_path):
    """ENDSCALE with quoted string tokens does NOT fire range issues.

    Phase 3.5: the ENDSCALE spec was rewritten to use string
    allowed_values for items 1-2. The OLD spec wrongly rejected
    NODIR/REVERS as out-of-range integers.
    """
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
ENDSCALE
  'NODIR'  'REVERS'  1  20  /
/
""")
    issues = lint_deck(deck).issues
    endscale_l2 = [
        i for i in issues
        if i.rule_id and i.rule_id.startswith("L2.ENDSCALE")
    ]
    assert endscale_l2 == [], (
        f"ENDSCALE with valid string tokens should pass, got: {endscale_l2}"
    )


@pytest.mark.unit
def test_l2_endscale_bad_string_fires(tmp_path):
    """ENDSCALE with an unknown scaling keyword fires L2.ENDSCALE.range."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
ENDSCALE
  'WIBBLE'  'NODIR'  1  20  /
/
""")
    issues = lint_deck(deck).issues
    matches = [
        i for i in issues
        if i.rule_id == "L2.ENDSCALE.range"
    ]
    assert len(matches) >= 1, f"expected L2.ENDSCALE.range, got {[i.rule_id for i in issues]}"
    assert "WIBBLE" in matches[0].message


# ---------------------------------------------------------------------- #
# Phase 3.5: L019 SUMMARY FU_* cross-check                               #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
def test_l019_summary_funvar_missing_fires(tmp_path):
    """SUMMARY section references FU_* not in FUNVAR fires L019 WARNING."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /

SUMMARY
FU_GOR
FU_WBHP
/
""")
    issues = lint_deck(deck).issues
    matches = [i for i in issues if i.rule_id == "L019"]
    assert len(matches) == 1, f"expected 1 L019, got {matches}"
    assert "FU_GOR" in matches[0].message
    assert "FU_WBHP" in matches[0].message


@pytest.mark.unit
def test_l019_no_false_positive_when_funvar_declares(tmp_path):
    """SUMMARY FU_* tokens that ARE in FUNVAR do NOT fire L019."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
FUNVAR
  FU_GOR  1.0  /
  FU_WBHP  1.0  /
/

SUMMARY
FU_GOR
FU_WBHP
/
""")
    issues = lint_deck(deck).issues
    matches = [i for i in issues if i.rule_id == "L019"]
    assert matches == [], f"unexpected L019: {matches}"


@pytest.mark.unit
def test_l019_ignores_udq_inline_fu_tokens(tmp_path):
    """FU_* tokens used in UDQ (SCHEDULE) do NOT need FUNVAR; L019 ignores them."""
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /

SUMMARY
-- No FU_* tokens here, so L019 should not fire.
FOPR
/

SCHEDULE
-- UDQ defines FU_GOR inline; no FUNVAR needed.
UDQ
ASSIGN FU_GOR 1.0 /
/
""")
    issues = lint_deck(deck).issues
    matches = [i for i in issues if i.rule_id == "L019"]
    assert matches == [], f"L019 should ignore UDQ-inline tokens, got: {matches}"
