"""Token and TokenKind definitions for the v2 linter.

This module is the vocabulary of the tokenizer. The tokenizer itself
(see tokenizer.py) emits a flat stream of `Token` objects with one of
the kinds defined here.

TokenKind semantics
-------------------

The 15 kinds partition the syntax of an Eclipse deck into lexically
distinct categories. Some kinds are column-sensitive (KEYWORD is
column-0 only; indented tokens are values even if they look like
keywords), some are shape-sensitive (FU_VAR must match the
`[ABCFGRSW]U[A-Z0-9_]+` shape), some are position-sensitive
(EOL is line-end).

Most tokens carry a `column_count` of 1. REPEAT_N_VALUE and
DEFAULT_N_STAR carry the integer `n` from `n*` or `n*value`, so the
parser can use the count as the source of truth for column indexing.

`line` and `col` give the token's location in the source file (1-indexed
for line, 0-indexed for col). `end_col` is exclusive. `raw` is the raw
text consumed from the source (after quote-trimming for STRING/DQUOTED).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TokenKind(str, Enum):
    """The 15 kinds of tokens an Eclipse deck can produce.

    Inherits from `str` so tokens can be serialized to JSON / YAML
    via their kind string and back to the enum.
    """

    # Section headers — column-0 token matching one of 8 section names,
    # optionally followed by trailing decoration (`GRID =====`). The
    # trailing decoration is consumed as part of the token's raw text.
    SECTION_HEADER = "SECTION_HEADER"

    # A keyword name — column-0 uppercase identifier that's not a section
    # header. Examples: WELSPECS, COMPDAT, DIMENS, PORO.
    KEYWORD = "KEYWORD"

    # An indented value that happens to be all-uppercase (e.g. column-1
    # token under an open block). Same lexical shape as KEYWORD but
    # syntactically a value. Examples: a column-2 item like `'LIQ'` is
    # a STRING; a column-1 PERMX is a VALUE.
    VALUE = "VALUE"

    # Single-quoted string. `'W1'`, `'LIQ'`, `'OPEN'`. May contain
    # escaped characters per Eclipse convention.
    STRING = "STRING"

    # Double-quoted string. Same semantics as STRING but rarer.
    DQUOTED = "DQUOTED"

    # Integer literal. `[-+]?[0-9]+` with no decimal/exponent/underscore.
    INT = "INT"

    # Floating-point literal. `[-+]?[0-9]*\.[0-9]+([eE][-+]?[0-9]+)?`.
    REAL = "REAL"

    # `n*` (default repeat). Always carries `column_count == n`. The
    # value at this column position is the prior column's default.
    DEFAULT_N_STAR = "DEFAULT_N_STAR"

    # `n*value` (repeated value). Always carries `column_count == n`.
    # The value is parsed from the suffix.
    REPEAT_N_VALUE = "REPEAT_N_VALUE"

    # FU_*/WU_*/GU_*/AU_*/BU_*/CU_*/RU_*/SU_* user-defined UDQ variable.
    # Shape: `[ABCFGRSW]U[A-Z0-9_]+` (must have a digit/underscore
    # immediately after the scope letter to avoid matching keywords
    # like RUNSPEC or WATER).
    FU_VAR = "FU_VAR"

    # Reserved for future WU-only handling; WU_ is currently bucketed
    # into FU_VAR since both are user-defined quantities.
    WU_VAR = "WU_VAR"

    # UDQ_* keyword-prefixed identifier. Less common than FU_VAR but
    # used in some UDQ expression contexts.
    UDQ_VAR = "UDQ_VAR"

    # ACTIONX_<name> label. Identifies an action block.
    ACTIONX_VAR = "ACTIONX_VAR"

    # PYACTION_<name> label. Identifies a Python action block.
    PYACTION_VAR = "PYACTION_VAR"

    # `--` to end of line. Trailing content is consumed as part of the
    # COMMENT token.
    COMMENT = "COMMENT"

    # Record terminator `/`. The terminator may sit on its own line or
    # at the end of the last record line; the parser handles both.
    TERMINATOR = "TERMINATOR"

    # End-of-line marker. Emitted at the end of every line for the
    # parser's line-orientation. Whitespace-only lines get just an EOL.
    EOL = "EOL"

    # Anything we couldn't classify. The text is preserved as-is so the
    # parser can still consume it. Pyrus emits `<UNKNOWN: ~text>` for
    # these. We just emit `UNKNOWN` with the raw text.
    UNKNOWN = "UNKNOWN"


@dataclass
class Token:
    """A single token from the tokenizer.

    Attributes:
        kind: The TokenKind.
        text: The token's payload (the keyword name, the integer's
            digits, the quoted string's contents with quotes stripped,
            etc.). For SECTION_HEADER with trailing decoration, this is
            just the section name; `raw` has the full text.
        raw: The exact characters consumed from the source. For STRING
            this includes the quotes; for SECTION_HEADER this includes
            the trailing decoration.
        line: 1-indexed line number.
        col: 0-indexed column where the token starts.
        end_col: Exclusive column (so `raw[0:end_col-col] == raw`).
        column_count: Number of parameter columns the token occupies.
            Always 1 except for DEFAULT_N_STAR and REPEAT_N_VALUE,
            where it's the `n` from `n*` or `n*value`.
    """

    kind: TokenKind
    text: str
    raw: str
    line: int
    col: int
    end_col: int
    column_count: int = 1

    def __repr__(self) -> str:
        return (
            f"Token({self.kind.name}, {self.text!r}, "
            f"line={self.line}, col={self.col}, count={self.column_count})"
        )

    def location_str(self) -> str:
        """Human-readable location string `line:col` (1-indexed)."""
        return f"{self.line}:{self.col + 1}"