"""Unit tests for the v2 parser (opm_ai.linter.v2.parser)."""

from __future__ import annotations

import pytest

from opm_ai.linter.v2.ast import Deck, Keyword, Record
from opm_ai.linter.v2.catalogue import KEYWORD_INDEX, known_keywords
from opm_ai.linter.v2.parser import parse
from opm_ai.linter.v2.spec import SectionName, SizeKind
from opm_ai.linter.v2.tokenizer import tokenize_file
from opm_ai.linter.v2.tokens import TokenKind


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kw(deck: Deck, section: SectionName, name: str) -> Keyword | None:
    s = deck.sections.get(section)
    if s is None:
        return None
    for k in s.keywords:
        if k.name == name:
            return k
    return None


# ---------------------------------------------------------------------------
# Catalogue tests
# ---------------------------------------------------------------------------


def test_catalogue_has_minimum_keyword_count():
    """The minimal catalogue must cover at least 50 keywords.

    Phase 2's gate: SPE1, SPE3, SPE5, SPE9, and the v1-known-bad
    fixtures collectively need ~50+ keywords to parse cleanly.
    """
    assert len(KEYWORD_INDEX) >= 50, (
        f"expected 50+ keywords in catalogue, got {len(KEYWORD_INDEX)}"
    )


def test_catalogue_covers_all_eight_sections():
    """At least one keyword is valid in each of the 8 sections."""
    for sec in SectionName:
        found = any(sec in spec.sections for spec in KEYWORD_INDEX.values())
        assert found, f"no keyword valid in section {sec.value}"


def test_catalogue_keyword_specs_are_well_formed():
    """Every KeywordSpec has a non-empty `name` and `sections`."""
    for name, spec in KEYWORD_INDEX.items():
        assert spec.name == name, (
            f"catalogue key '{name}' mismatches spec.name '{spec.name}'"
        )
        assert spec.sections, f"{name} has no valid sections"
        assert spec.size_kind in SizeKind, (
            f"{name} has invalid size_kind {spec.size_kind}"
        )


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------


def test_minimal_deck_parses_cleanly():
    text = """\
RUNSPEC
DIMENS
  3 3 3 /
OIL

GRID
DX
  27*100 /

SCHEDULE
END
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)

    assert list(deck.sections.keys()) == [
        SectionName.RUNSPEC,
        SectionName.GRID,
        SectionName.SCHEDULE,
    ]
    assert _kw(deck, SectionName.RUNSPEC, "DIMENS") is not None
    assert _kw(deck, SectionName.RUNSPEC, "OIL") is not None
    assert _kw(deck, SectionName.GRID, "DX") is not None


def test_section_order_enforced_backwards():
    """A section that appears out of canonical order is flagged."""
    text = """\
RUNSPEC
OIL

GRID
DX
  27*100 /

RUNSPEC   -- backwards: RUNSPEC after GRID
WATER
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)

    # RUNSPEC re-entry should generate a parse error
    assert any("canonical order" in e for e in deck.parse_errors), (
        f"expected canonical-order error; got {deck.parse_errors}"
    )


def test_eight_section_headers_recognized():
    """All 8 sections are recognized when they appear in order."""
    text = """\
RUNSPEC
DIMENS 3 3 3 /

GRID
DX
  27*100 /

EDIT
EQUALS
  PERMX 1 1 1 1 1 1 1000 /

PROPS
SWOF
  0.0 0.0 1.0
  1.0 1.0 0.0 /

REGIONS
FIPNUM
  27*1 /

SOLUTION
EQUIL
  300 100 400 0 0 0 0 0 /

SUMMARY
FOPR

SCHEDULE
WELSPECS
  'W1' 'G' 1 1 1.0 'LIQ' /
END
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    expected = [
        SectionName.RUNSPEC,
        SectionName.GRID,
        SectionName.EDIT,
        SectionName.PROPS,
        SectionName.REGIONS,
        SectionName.SOLUTION,
        SectionName.SUMMARY,
        SectionName.SCHEDULE,
    ]
    assert list(deck.sections.keys()) == expected


# ---------------------------------------------------------------------------
# Per-size_kind dispatch
# ---------------------------------------------------------------------------


def test_fixed_kind_dimens():
    """DIMENS is `fixed` with record_count=1, item_count=3."""
    text = """\
RUNSPEC
DIMENS
  3 3 3 /
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    kw = _kw(deck, SectionName.RUNSPEC, "DIMENS")
    assert kw is not None
    assert kw.spec.size_kind == SizeKind.FIXED
    assert len(kw.records) == 1
    items = [t.text for t in kw.records[0].items]
    assert items == ["3", "3", "3"]
    assert kw.records[0].column_count_total() == 3


def test_list_kind_welspecs_multiple_records():
    """WELSPECS is `list`; multiple records each terminated by `/`."""
    text = """\
SCHEDULE
WELSPECS
  'W1' 'G' 1 1 1.0 'LIQ' /
  'W2' 'G' 2 2 1.0 'LIQ' /
  'W3' 'G' 3 3 1.0 'GAS' /
END
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    kw = _kw(deck, SectionName.SCHEDULE, "WELSPECS")
    assert kw is not None
    assert kw.spec.size_kind == SizeKind.LIST
    assert len(kw.records) == 3
    # Each record has 6 items.
    for rec in kw.records:
        assert len(rec.items) == 6
        assert rec.terminator is not None


def test_array_kind_dx():
    """DX is `array`; column_count_total reflects n*value repeat."""
    text = """\
GRID
DX
  27*100 /
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    kw = _kw(deck, SectionName.GRID, "DX")
    assert kw is not None
    assert kw.spec.size_kind == SizeKind.ARRAY
    # Single record with one REPEAT_N_VALUE token of column_count 27.
    assert len(kw.records) == 1
    rec = kw.records[0]
    assert rec.column_count_total() == 27


def test_none_kind_end():
    """END is `none`; zero records."""
    text = """\
RUNSPEC
END
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    kw = _kw(deck, SectionName.RUNSPEC, "END")
    assert kw is not None
    assert kw.spec.size_kind == SizeKind.NONE
    assert len(kw.records) == 0


# ---------------------------------------------------------------------------
# Errors and edge cases
# ---------------------------------------------------------------------------


def test_unknown_keyword_does_not_crash():
    """An unknown keyword at column 0 is recorded with unknown_reason."""
    text = """\
RUNSPEC
FOOBAR /
DIMENS
  3 3 3 /
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    kw = _kw(deck, SectionName.RUNSPEC, "FOOBAR")
    assert kw is not None
    assert "unknown" in kw.unknown_reason.lower()


def test_fu_var_at_column0_becomes_fu_var_decl():
    """FU_* tokens at column 0 in SUMMARY become FU_VAR_DECL keywords.

    Regression: previously these were absorbed into the previous
    keyword's record (L202). Each FU_* declaration is now its own
    keyword with the FU_DECL spec (size_kind=NONE).
    """
    text = """\
RUNSPEC
DIMENS 2 2 2 /

SUMMARY
INCLUDE
 'include/foo' /
FU_GAS
FU_GAS_P
FUGASMX
END
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    summary = deck.sections[SectionName.SUMMARY]
    names = [k.name for k in summary.keywords]
    assert "INCLUDE" in names
    assert "FU_GAS" in names
    assert "FU_GAS_P" in names
    assert "FUGASMX" in names
    # FU_GAS and FU_GAS_P are FU_VAR_DECL — spec is FU_DECL.
    fu_gas = [k for k in summary.keywords if k.name == "FU_GAS"][0]
    fu_gas_p = [k for k in summary.keywords if k.name == "FU_GAS_P"][0]
    assert fu_gas.spec is not None
    assert fu_gas.spec.name == "FU_VAR_DECL"
    assert fu_gas_p.spec is not None
    assert fu_gas_p.spec.name == "FU_VAR_DECL"
    # And they have no records (size_kind=NONE).
    assert fu_gas.records == []
    assert fu_gas_p.records == []
    # FUGASMX is still unknown (not an FU_VAR_DECL pattern).
    fugasmx = [k for k in summary.keywords if k.name == "FUGASMX"][0]
    assert fugasmx.spec is None


def test_funvar_records_contain_fu_var_names_as_values():
    """FUNVAR's record items (FU_*, WU_*, GU_*) are values, not keywords.

    Regression: a previous fix made column-0 FU_* tokens always
    new keywords, which broke FUNVAR parsing (each FU_* name
    should be a record item, not a separate keyword).
    """
    text = """\
RUNSPEC
DIMENS 2 2 2 /

SUMMARY
FUNVAR
FU_OIL_RATE WU_OIL_RATE GU_OIL_RATE /

END
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    funvar = _kw(deck, SectionName.SUMMARY, "FUNVAR")
    assert funvar is not None
    assert len(funvar.records) == 1
    items = [t.text for t in funvar.records[0].items]
    assert items == ["FU_OIL_RATE", "WU_OIL_RATE", "GU_OIL_RATE"]


def test_wrong_section_records_unknown_reason():
    """A keyword in the wrong section is flagged, but parsing continues."""
    text = """\
GRID
WELLDIMS
  1 1 1 1 /
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    kw = _kw(deck, SectionName.GRID, "WELLDIMS")
    assert kw is not None
    assert "not valid in section" in kw.unknown_reason


def test_value_before_any_keyword_is_parse_error():
    """A value token before any keyword records a parse error."""
    text = """\
RUNSPEC
100 200 300 /
DIMENS
  3 3 3 /
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    # The 100 200 300 are value tokens before any keyword is opened
    # (DIMENS appears after them). At least one parse error should fire.
    assert any(
        "outside any keyword" in e for e in deck.parse_errors
    ), f"expected parse error; got {deck.parse_errors}"


def test_deck_keyword_count_sums_correctly():
    """deck.keyword_count() returns the total across all sections."""
    text = """\
RUNSPEC
DIMENS 3 3 3 /
OIL
WATER

GRID
DX
  27*100 /

SCHEDULE
WELSPECS
  'W1' 'G' 1 1 1.0 'LIQ' /
END
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    # 3 RUNSPEC + 1 GRID + 2 SCHEDULE = 6
    expected_total = 6
    assert deck.keyword_count() == expected_total
    # deck.keyword_count() must equal the sum across sections.
    total = sum(len(s.keywords) for s in deck.sections.values())
    assert deck.keyword_count() == total


# ---------------------------------------------------------------------------
# Multi-record and section transitions
# ---------------------------------------------------------------------------


def test_welspecs_records_have_correct_items():
    """Each WELSPECS record has the 6 expected items."""
    text = """\
SCHEDULE
WELSPECS
  'W1' 'G' 1 1 1.0 'LIQ' /
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    kw = _kw(deck, SectionName.SCHEDULE, "WELSPECS")
    rec = kw.records[0]
    item_texts = [t.text for t in rec.items]
    assert item_texts == ["W1", "G", "1", "1", "1.0", "LIQ"]


def test_block_terminator_closes_array_keyword():
    """A standalone `/` line closes an array keyword's block."""
    text = """\
GRID
DX
  27*100
/
"""
    tokens = tokenize_file(text)
    deck = parse(tokens)
    kw = _kw(deck, SectionName.GRID, "DX")
    # The array's block may collect records until the standalone `/`.
    # The parser may close the keyword on the standalone `/`.
    assert kw is not None
    assert len(kw.records) >= 1