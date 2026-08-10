"""Unit tests for the v2 tokenizer (opm_ai.linter.v2.tokenizer)."""

from __future__ import annotations

from pathlib import Path

import pytest

from opm_ai.linter.v2.tokens import Token, TokenKind
from opm_ai.linter.v2.tokenizer import (
    iter_tokens,
    tokenize_file,
    tokenize_line,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kinds(tokens: list[Token]) -> list[str]:
    return [t.kind.name for t in tokens]


def _texts(tokens: list[Token]) -> list[str]:
    return [t.text for t in tokens]


def _first(tokens: list[Token], kind: TokenKind) -> Token:
    for t in tokens:
        if t.kind == kind:
            return t
    raise AssertionError(f"no {kind.name} token in {_kinds(tokens)}")


# ---------------------------------------------------------------------------
# T1.1: TokenKind enum
# ---------------------------------------------------------------------------


def test_token_kind_has_correct_members():
    """TokenKind has the kinds defined in the Phase 1 spec.

    The spec lists 17 kinds in FUTURE_IMPLEMENTATION.md T1.1
    (section header table). The doc text mentioned 15 but the table
    has 17. We test the *presence* of each kind, not the exact count,
    so adding future kinds doesn't break this test.
    """
    expected = {
        "SECTION_HEADER",
        "KEYWORD",
        "VALUE",
        "STRING",
        "DQUOTED",
        "INT",
        "REAL",
        "DEFAULT_N_STAR",
        "REPEAT_N_VALUE",
        "FU_VAR",
        "UDQ_VAR",
        "ACTIONX_VAR",
        "PYACTION_VAR",
        "COMMENT",
        "TERMINATOR",
        "EOL",
        "UNKNOWN",
    }
    actual = {k.name for k in TokenKind}
    assert expected <= actual, (
        f"missing kinds: {expected - actual}"
    )


def test_token_kind_members_are_strings():
    """TokenKind inherits from str so tokens serialize cleanly."""
    for k in TokenKind:
        assert isinstance(k.value, str)


# ---------------------------------------------------------------------------
# T1.2 / T1.3: single-line and multi-line tokenizers
# ---------------------------------------------------------------------------


def test_empty_line_emits_only_eol():
    tokens = tokenize_line("", line_no=1)
    assert _kinds(tokens) == ["EOL"]
    assert tokens[0].line == 1


def test_whitespace_only_line_emits_only_eol():
    tokens = tokenize_line("    ", line_no=5)
    assert _kinds(tokens) == ["EOL"]
    assert tokens[0].line == 5


def test_comment_line():
    tokens = tokenize_line("-- this is a comment")
    assert _kinds(tokens) == ["COMMENT", "EOL"]
    assert tokens[0].text == ""
    assert tokens[0].raw == "-- this is a comment"


def test_indented_comment_line():
    """An indented comment is still a comment."""
    tokens = tokenize_line("   -- indented comment")
    assert _kinds(tokens) == ["COMMENT", "EOL"]


# ---------------------------------------------------------------------------
# T1.5: quoted strings
# ---------------------------------------------------------------------------


def test_single_quoted_string():
    tokens = tokenize_line("'W1'")
    assert _kinds(tokens) == ["STRING", "EOL"]
    s = tokens[0]
    assert s.text == "W1"
    assert s.raw == "'W1'"


def test_double_quoted_string():
    tokens = tokenize_line('"W1"')
    assert _kinds(tokens) == ["DQUOTED", "EOL"]
    assert tokens[0].text == "W1"


def test_string_with_escape():
    tokens = tokenize_line(r"'W\'1'")
    assert _kinds(tokens) == ["STRING", "EOL"]
    assert tokens[0].text == "W'1"


def test_string_with_newline_escape():
    tokens = tokenize_line(r"'line1\nline2'")
    assert _kinds(tokens) == ["STRING", "EOL"]
    assert tokens[0].text == "line1\nline2"


def test_unterminated_string_is_unknown():
    tokens = tokenize_line("'W1")
    assert _kinds(tokens) == ["UNKNOWN", "EOL"]
    assert tokens[0].raw == "'W1"


# ---------------------------------------------------------------------------
# T1.6 / T1.7: comments and terminators
# ---------------------------------------------------------------------------


def test_mid_line_comment_stops_scanning():
    """A mid-line `--` ends token scanning for the rest of the line."""
    tokens = tokenize_line("DIMENS 10 10 3 / -- dimensions here")
    assert _kinds(tokens) == [
        "KEYWORD",
        "INT",
        "INT",
        "INT",
        "TERMINATOR",
        "COMMENT",
        "EOL",
    ]
    # The COMMENT token's raw includes everything from the `--` onward,
    # including the leading space before the `--`.
    assert tokens[-2].raw == " -- dimensions here"


def test_terminator_is_single_slash():
    tokens = tokenize_line("/")
    assert _kinds(tokens) == ["TERMINATOR", "EOL"]


def test_terminator_mid_line():
    tokens = tokenize_line("WELSPECS 'W1' 'G' 1 1 1.0 'LIQ' /")
    assert tokens[-2].kind == TokenKind.TERMINATOR


# ---------------------------------------------------------------------------
# T1.4: n* and n*value
# ---------------------------------------------------------------------------


def test_default_n_star():
    """`8*` is a DEFAULT_N_STAR with column_count=8."""
    tokens = tokenize_line("PORO 8* /")
    rep = _first(tokens, TokenKind.DEFAULT_N_STAR)
    assert rep.text == ""
    assert rep.column_count == 8


def test_repeat_n_value_int():
    """`8*100` is a REPEAT_N_VALUE with column_count=8, text='100'."""
    tokens = tokenize_line("DX 8*100 /")
    rep = _first(tokens, TokenKind.REPEAT_N_VALUE)
    assert rep.text == "100"
    assert rep.column_count == 8


def test_repeat_n_value_real():
    """`8*1.5` is a REPEAT_N_VALUE, text='1.5', column_count=8."""
    tokens = tokenize_line("DX 8*1.5 /")
    rep = _first(tokens, TokenKind.REPEAT_N_VALUE)
    assert rep.text == "1.5"
    assert rep.column_count == 8


def test_repeat_n_value_with_sign():
    """`8*+1.5` and `8*-1.5` parse the sign into the value."""
    for word in ("8*+1.5", "8*-1.5"):
        tokens = tokenize_line(f"DX {word} /")
        rep = _first(tokens, TokenKind.REPEAT_N_VALUE)
        assert rep.column_count == 8
        assert rep.text in ("+1.5", "-1.5")


def test_repeat_n_value_with_exponent():
    """`5*1.5e-3` has an exponent."""
    tokens = tokenize_line("DX 5*1.5e-3 /")
    rep = _first(tokens, TokenKind.REPEAT_N_VALUE)
    assert rep.text == "1.5e-3"
    assert rep.column_count == 5


# ---------------------------------------------------------------------------
# T1.8: section headers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS", "SOLUTION", "SUMMARY", "SCHEDULE"],
)
def test_section_headers_recognized(name):
    tokens = tokenize_line(name)
    assert _kinds(tokens) == ["SECTION_HEADER", "EOL"]
    assert tokens[0].text == name


def test_section_header_with_trailing_decoration():
    """`GRID ======` and `RUNSPEC -----` are valid section headers."""
    tokens = tokenize_line("GRID =====")
    assert _kinds(tokens) == ["SECTION_HEADER", "EOL"]
    assert tokens[0].text == "GRID"  # name stripped
    assert "=====" in tokens[0].raw  # decoration kept in raw


def test_section_header_with_dashes():
    tokens = tokenize_line("RUNSPEC -----")
    assert _kinds(tokens) == ["SECTION_HEADER", "EOL"]


def test_lowercase_word_is_unknown():
    """`runspec` (lowercase) is column-0 but doesn't match the
    uppercase KEYWORD pattern, so it's UNKNOWN."""
    tokens = tokenize_line("runspec")
    assert _kinds(tokens) == ["UNKNOWN", "EOL"]


# ---------------------------------------------------------------------------
# T1.9: keyword vs value column rule
# ---------------------------------------------------------------------------


def test_column_zero_keyword():
    tokens = tokenize_line("DIMENS")
    assert tokens[0].kind == TokenKind.KEYWORD
    assert tokens[0].col == 0


def test_indented_uppercase_is_value():
    """A column-2 uppercase token is a VALUE, not a KEYWORD."""
    tokens = tokenize_line("  PORO 100")
    assert tokens[0].kind == TokenKind.VALUE
    assert tokens[0].col == 2


def test_real_number_with_sign():
    tokens = tokenize_line("-1.5")
    assert tokens[0].kind == TokenKind.REAL
    assert tokens[0].text == "-1.5"


def test_real_with_exponent():
    tokens = tokenize_line("1.5e-3")
    assert tokens[0].kind == TokenKind.REAL
    assert tokens[0].text == "1.5e-3"


def test_integer():
    tokens = tokenize_line("42")
    assert tokens[0].kind == TokenKind.INT
    assert tokens[0].text == "42"


def test_negative_integer():
    tokens = tokenize_line("-7")
    assert tokens[0].kind == TokenKind.INT
    assert tokens[0].text == "-7"


# ---------------------------------------------------------------------------
# T1.10: FU_VAR / UDQ_VAR / ACTIONX_VAR / PYACTION_VAR
# ---------------------------------------------------------------------------


def test_fu_var_with_underscore():
    tokens = tokenize_line("FU_MYVAR")
    assert _kinds(tokens) == ["FU_VAR", "EOL"]


def test_fu_var_with_digit_after_scope():
    """`FU123` is a FU_VAR (digit immediately after scope letter U)."""
    tokens = tokenize_line("FU123")
    assert _kinds(tokens) == ["FU_VAR", "EOL"]


def test_wu_var_recognized():
    """`WU_WVAR` is a FU_VAR (FU_VAR covers all scope letters)."""
    tokens = tokenize_line("WU_WVAR")
    assert _kinds(tokens) == ["FU_VAR", "EOL"]


def test_wumvar_without_underscore_is_keyword():
    """`WUMVAR` (no digit/underscore after scope) is a plain KEYWORD."""
    tokens = tokenize_line("WUMVAR")
    assert _kinds(tokens) == ["KEYWORD", "EOL"]


def test_runspec_is_not_fu_var():
    """`RUNSPEC` must NOT match FU_VAR (no digit/underscore after U)."""
    tokens = tokenize_line("RUNSPEC")
    assert _kinds(tokens) == ["SECTION_HEADER", "EOL"]


def test_water_is_not_fu_var():
    """`WATER` must NOT match FU_VAR (no FU_ prefix)."""
    tokens = tokenize_line("WATER")
    assert _kinds(tokens) == ["KEYWORD", "EOL"]


def test_udq_var():
    tokens = tokenize_line("UDQ_MYVAR")
    assert _kinds(tokens) == ["UDQ_VAR", "EOL"]


def test_actionx_var():
    tokens = tokenize_line("ACTIONX_MY_ACTION")
    assert _kinds(tokens) == ["ACTIONX_VAR", "EOL"]


def test_pyaction_var():
    tokens = tokenize_line("PYACTION_MY_ACTION")
    assert _kinds(tokens) == ["PYACTION_VAR", "EOL"]


# ---------------------------------------------------------------------------
# T1.3: multi-line tokenize_file and iter_tokens
# ---------------------------------------------------------------------------


def test_tokenize_file_tracks_line_numbers():
    text = """DIMENS 10 10 3 /
DX 8*100 /
"""
    tokens = tokenize_file(text)
    # Filter to non-EOL
    non_eol = [t for t in tokens if t.kind != TokenKind.EOL]
    # non_eol: [DIMENS l1, 10 l1, 10 l1, 3 l1, / l1, DX l2, 8*100 l2, / l2]
    assert non_eol[0].line == 1
    assert non_eol[0].text == "DIMENS"
    assert non_eol[5].line == 2
    assert non_eol[5].text == "DX"
    assert non_eol[6].line == 2
    assert non_eol[6].kind == TokenKind.REPEAT_N_VALUE
    assert non_eol[6].text == "100"


def test_tokenize_file_handles_blank_lines():
    text = "DIMENS 10 10 3 /\n\nGRID\n"
    tokens = tokenize_file(text)
    # The blank line in the middle should still produce an EOL token.
    assert any(
        t.kind == TokenKind.EOL and t.line == 2 for t in tokens
    ), "blank line should produce an EOL"


def test_tokenize_file_crlf():
    text = "DIMENS 10 10 3 /\r\nDX 8*100 /\r\n"
    tokens = tokenize_file(text)
    non_eol = [t for t in tokens if t.kind != TokenKind.EOL]
    assert non_eol[0].line == 1
    assert non_eol[5].line == 2  # DX
    assert non_eol[6].line == 2  # 8*100


def test_iter_tokens_yields_same_as_tokenize_file():
    text = "DIMENS 10 10 3 /\nDX 8*100 /\n"
    from_file = tokenize_file(text)
    from_iter = list(iter_tokens(text))
    assert [(t.kind, t.text) for t in from_file] == [
        (t.kind, t.text) for t in from_iter
    ]


# ---------------------------------------------------------------------------
# T1.11: round-trip test (tokens -> text -> tokens)
# ---------------------------------------------------------------------------


def test_round_trip_simple_keyword_line():
    """Reconstruct text from non-EOL tokens and re-tokenize; result equals."""
    text = "DIMENS 10 10 3 /"
    tokens = tokenize_line(text)
    # Filter EOL/COMMENT
    payload = [t for t in tokens if t.kind not in (TokenKind.EOL, TokenKind.COMMENT)]
    reconstructed = " ".join(t.raw for t in payload)
    # Re-tokenize the reconstructed text (tokens are space-separated).
    rt_tokens = tokenize_line(reconstructed)
    assert [(t.kind, t.text) for t in tokens if t.kind != TokenKind.EOL] == [
        (t.kind, t.text) for t in rt_tokens if t.kind != TokenKind.EOL
    ]


def test_round_trip_repeat_value():
    """`8*100` round-trips: token -> raw -> re-tokenize -> same token."""
    tokens = tokenize_line("8*100")
    rt = tokenize_line(tokens[0].raw)
    assert rt[0].kind == TokenKind.REPEAT_N_VALUE
    assert rt[0].text == "100"
    assert rt[0].column_count == 8


def test_round_trip_string_with_escape():
    """A string with `\'` round-trips: the text is the unescaped form."""
    tokens = tokenize_line(r"'W\'1'")
    rt = tokenize_line(tokens[0].raw)
    assert rt[0].kind == TokenKind.STRING
    assert rt[0].text == "W'1"


# ---------------------------------------------------------------------------
# Multi-line realistic deck
# ---------------------------------------------------------------------------


def test_realistic_spe1_excerpt():
    text = """\
-- SPE1 - Case 1
RUNSPEC

TITLE
   SPE1 - CASE 1
/

DIMENS
  10 10 3 /
OIL
GAS
WATER

GRID
DX
  300*100 /
"""
    tokens = tokenize_file(text)
    # Sanity: section headers are recognized, key keywords are present.
    section_headers = [t for t in tokens if t.kind == TokenKind.SECTION_HEADER]
    assert {t.text for t in section_headers} >= {"RUNSPEC", "GRID"}

    keywords = [t for t in tokens if t.kind == TokenKind.KEYWORD]
    assert {t.text for t in keywords} >= {
        "TITLE",
        "DIMENS",
        "OIL",
        "GAS",
        "WATER",
        "DX",
    }

    # The 300*100 on the last data line is a REPEAT_N_VALUE with count=300.
    rep = _first(tokens, TokenKind.REPEAT_N_VALUE)
    assert rep.column_count == 300
    assert rep.text == "100"