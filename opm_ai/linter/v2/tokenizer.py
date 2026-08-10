"""Hand-rolled tokenizer for the v2 linter.

Consumes deck text and produces a flat `Token` stream (see tokens.py).
The tokenizer is line-oriented: it emits an EOL token at the end of
every source line, including whitespace-only and comment-only lines.

Algorithm (per line):
  1. Skip leading whitespace, remembering the starting column.
  2. If the line is empty after whitespace, emit just an EOL.
  3. If the line starts with `--`, consume to EOL as a COMMENT,
     then emit an EOL.
  4. If the line starts with one of the 8 section names (RUNSPEC,
     GRID, EDIT, PROPS, REGIONS, SOLUTION, SUMMARY, SCHEDULE) and
     matches the section-header shape, consume the section name plus
     any trailing non-comment text as a SECTION_HEADER token, then EOL.
  5. Otherwise, scan whitespace-delimited tokens left to right:
     - Quoted string (single or double quote): consume to matching
       quote, emit STRING or DQUOTED.
     - `--`: consume to EOL as COMMENT, then EOL.
     - `/`: emit TERMINATOR (just the slash).
     - `n*` or `n*value`: emit DEFAULT_N_STAR or REPEAT_N_VALUE with
       column_count=n.
     - Digit: emit INT or REAL.
     - Letter: emit KEYWORD (if column 0) / VALUE (otherwise) /
       FU_VAR / etc. based on shape.

The tokenizer is a single-pass character scanner. No backtracking is
performed; tokens are emitted as soon as they can be classified.

Section-header special case: section headers may have trailing
decoration (`GRID =====`, `RUNSPEC ---------------`). The decoration is
consumed as part of the SECTION_HEADER token's raw text but stripped
from `text` (which holds only the section name). This matches Eclipse's
"match leading token only, ignore trailing decoration" rule (per
OPM-flow-editor-support).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from .tokens import Token, TokenKind

# Section header names — must match exactly (case-sensitive, uppercase).
_SECTION_NAMES = (
    "RUNSPEC",
    "GRID",
    "EDIT",
    "PROPS",
    "REGIONS",
    "SOLUTION",
    "SUMMARY",
    "SCHEDULE",
)

# UDQ user-variable shape. Must have a digit or underscore immediately
# after the scope letter; this excludes false-positive matches on
# keywords like RUNSPEC (R, U, then NSPEC — no digit/underscore at the
# scope position) or WATER (no FU-prefix).
# Scope letters: A, B, C, F, G, R, S, W (per OPM Flow spec).
_FU_VAR_RE = re.compile(r"[ABCFGRSW]U[_0-9][A-Z0-9_]*\Z")

# UDQ_* keyword-prefixed identifier. Less common than FU_VAR.
_UDQ_VAR_RE = re.compile(r"UDQ_[A-Z0-9_]+\Z")

# ACTIONX_<name> label.
_ACTIONX_VAR_RE = re.compile(r"ACTIONX_[A-Z0-9_]+\Z")

# PYACTION_<name> label.
_PYACTION_VAR_RE = re.compile(r"PYACTION_[A-Z0-9_]+\Z")

# Plain keyword/identifier: uppercase letters/digits/+/-/_/starting with letter.
# Length 1-15 matches the OPM extension's KEYWORD pattern.
_KEYWORD_RE = re.compile(r"[A-Z][A-Z0-9_+\-]{0,15}\Z")

# Repeat/default pattern.
_N_STAR_VALUE_RE = re.compile(r"(\d+)\*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)?\Z")

# Section header pattern: section name followed by whitespace or EOL or
# trailing non-comment decoration. Capture the section name.
_SECTION_HEADER_RE = re.compile(
    r"(RUNSPEC|GRID|EDIT|PROPS|REGIONS|SOLUTION|SUMMARY|SCHEDULE)(?:\s.*)?\Z",
    re.DOTALL,
)

# Integer and real literal patterns.
_INT_RE = re.compile(r"[-+]?[0-9]+\Z")
_REAL_RE = re.compile(r"[-+]?[0-9]*\.[0-9]+(?:[eE][-+]?[0-9]+)?\Z")


def _classify_word(word: str, at_column_zero: bool) -> TokenKind:
    """Classify a whitespace-delimited non-numeric word.

    Order matters: FU_VAR is checked first (most specific), then UDQ_VAR,
    ACTIONX_VAR, PYACTION_VAR, then KEYWORD/VALUE (the catch-all).
    """
    if _FU_VAR_RE.match(word):
        return TokenKind.FU_VAR
    if _UDQ_VAR_RE.match(word):
        return TokenKind.UDQ_VAR
    if _ACTIONX_VAR_RE.match(word):
        return TokenKind.ACTIONX_VAR
    if _PYACTION_VAR_RE.match(word):
        return TokenKind.PYACTION_VAR
    if _KEYWORD_RE.match(word):
        return TokenKind.KEYWORD if at_column_zero else TokenKind.VALUE
    return TokenKind.UNKNOWN


def tokenize_line(line: str, line_no: int = 1) -> list[Token]:
    """Tokenize a single line of deck text.

    Args:
        line: The line text (without trailing newline).
        line_no: 1-indexed line number for location tracking.

    Returns:
        List of tokens. Always ends with an EOL token, even for empty
        or whitespace-only lines.
    """
    tokens: list[Token] = []
    i = 0
    n = len(line)

    # Skip leading whitespace; remember starting column.
    while i < n and line[i] in " \t":
        i += 1

    if i >= n:
        # Empty or whitespace-only line.
        tokens.append(Token(TokenKind.EOL, "", "", line_no, i, i))
        return tokens

    # Comment-only line.
    if line[i] == "-" and i + 1 < n and line[i + 1] == "-":
        tokens.append(Token(TokenKind.COMMENT, "", line[i:], line_no, i, n))
        tokens.append(Token(TokenKind.EOL, "", "", line_no, n, n))
        return tokens

    # Section header — only valid at column 0 and only if the line
    # starts with one of the 8 section names. Trailing decoration
    # (`======`, `---------------`) is consumed but stripped from text.
    if i == 0:
        m = _SECTION_HEADER_RE.match(line)
        if m is not None:
            section_name = m.group(1)
            tokens.append(
                Token(
                    TokenKind.SECTION_HEADER,
                    section_name,
                    line,
                    line_no,
                    0,
                    n,
                )
            )
            tokens.append(Token(TokenKind.EOL, "", "", line_no, n, n))
            return tokens

    # Token scan loop.
    while i < n:
        # Skip intra-line whitespace.
        if line[i] in " \t":
            i += 1
            continue

        # Comment mid-line.
        if line[i] == "-" and i + 1 < n and line[i + 1] == "-":
            # Include any leading whitespace so the comment raw text
            # round-trips (text -> tokens -> raw reconstructs the line).
            # Find the start of whitespace before the `--`.
            comment_start = i
            while comment_start > 0 and line[comment_start - 1] in " \t":
                comment_start -= 1
            tokens.append(
                Token(TokenKind.COMMENT, "", line[comment_start:], line_no, comment_start, n)
            )
            break

        # Terminator.
        if line[i] == "/":
            tokens.append(Token(TokenKind.TERMINATOR, "/", "/", line_no, i, i + 1))
            i += 1
            continue

        # Single-quoted string.
        if line[i] == "'":
            end = _find_quote(line, i, "'")
            if end == -1:
                # Unterminated quote — emit as UNKNOWN with whatever
                # we have up to end of line.
                tokens.append(
                    Token(TokenKind.UNKNOWN, line[i:], line[i:], line_no, i, n)
                )
                i = n
                continue
            content = _unescape(line[i + 1 : end])
            tokens.append(
                Token(
                    TokenKind.STRING,
                    content,
                    line[i : end + 1],
                    line_no,
                    i,
                    end + 1,
                )
            )
            i = end + 1
            continue

        # Double-quoted string.
        if line[i] == '"':
            end = _find_quote(line, i, '"')
            if end == -1:
                tokens.append(
                    Token(TokenKind.UNKNOWN, line[i:], line[i:], line_no, i, n)
                )
                i = n
                continue
            content = _unescape(line[i + 1 : end])
            tokens.append(
                Token(
                    TokenKind.DQUOTED,
                    content,
                    line[i : end + 1],
                    line_no,
                    i,
                    end + 1,
                )
            )
            i = end + 1
            continue

        start = i
        # Consume one whitespace-delimited chunk.
        while i < n and line[i] not in " \t":
            if line[i] == "/" and i > start:
                # `/` mid-word is division operator — but in Eclipse
                # practice, division only appears inside UDQ expressions
                # where the token is already being consumed as a single
                # word. For the simple case, `/` terminates the word.
                # We treat the `/` as the next token (TERMINATOR).
                break
            i += 1
        word = line[start:i]

        if not word:
            # Shouldn't happen, but guard against empty token.
            continue

        # n*value or n* repeat/default.
        m = _N_STAR_VALUE_RE.match(word)
        if m:
            n_count = int(m.group(1))
            value = m.group(2)
            if value is None:
                kind = TokenKind.DEFAULT_N_STAR
                text = ""
            else:
                kind = TokenKind.REPEAT_N_VALUE
                text = value
            tokens.append(
                Token(
                    kind,
                    text,
                    word,
                    line_no,
                    start,
                    i,
                    column_count=n_count,
                )
            )
            continue

        # Integer literal.
        if _INT_RE.match(word):
            tokens.append(Token(TokenKind.INT, word, word, line_no, start, i))
            continue

        # Real literal.
        if _REAL_RE.match(word):
            tokens.append(Token(TokenKind.REAL, word, word, line_no, start, i))
            continue

        # Word: classify as FU_VAR / UDQ_VAR / ACTIONX_VAR / PYACTION_VAR /
        # KEYWORD (col 0) / VALUE (col > 0) / UNKNOWN.
        at_col0 = start == 0
        kind = _classify_word(word, at_col0)
        tokens.append(Token(kind, word, word, line_no, start, i))

    tokens.append(Token(TokenKind.EOL, "", "", line_no, n, n))
    return tokens


def _find_quote(line: str, start: int, quote: str) -> int:
    """Find the matching closing quote, handling backslash escapes.

    Returns the index of the closing quote, or -1 if unterminated.
    """
    i = start + 1
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line):
            i += 2
            continue
        if line[i] == quote:
            return i
        i += 1
    return -1


def _unescape(text: str) -> str:
    """Unescape Eclipse backslash escapes in a quoted string.

    Eclipse convention: `\\x` → `x` for any x. We support the common
    escapes (\\\\, \\', \\", \\n, \\t) but pass through unknown escapes
    verbatim (don't drop the backslash).
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "\\":
                out.append("\\")
            elif nxt == "'":
                out.append("'")
            elif nxt == '"':
                out.append('"')
            else:
                # Unknown escape — keep both chars verbatim.
                out.append(text[i])
                out.append(nxt)
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def tokenize_file(
    text: str,
    source_file: Path | str | None = None,
) -> list[Token]:
    """Tokenize a multi-line deck text.

    Args:
        text: The full deck text (may contain newlines).
        source_file: Optional path for diagnostic messages; not used
            for location tracking (location is line-relative).

    Returns:
        Flat list of tokens. Line numbers are 1-indexed.
    """
    tokens: list[Token] = []
    # splitlines() handles \n, \r\n, and \r uniformly and does not
    # include the line separator in the output — which is what we want
    # because each line is processed independently.
    for line_no, line in enumerate(text.splitlines(), start=1):
        tokens.extend(tokenize_line(line, line_no))
    return tokens


def iter_tokens(text: str) -> Iterator[Token]:
    """Iterator form of tokenize_file, for streaming consumers."""
    for line_no, line in enumerate(text.splitlines(), start=1):
        yield from tokenize_line(line, line_no)