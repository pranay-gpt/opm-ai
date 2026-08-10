"""AST dataclasses for the v2 linter.

The parser produces a `Deck` (the root) containing `Section` objects
(in canonical order), each containing `Keyword` objects, each
containing `Record` objects, each containing `Token` objects (from
the tokenizer). All nodes carry source-location info.

This is the same shape as OPM-ext's `parsedDeck` /
`parsedKeywordSection` / `parsedKeyword` (analysis.ts), but typed
as Python dataclasses with `line`/`col` for source tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .spec import SectionName
from .tokens import Token


@dataclass
class Record:
    """A single record (one row) of a keyword.

    A keyword has 1+ records. A `fixed`-kind keyword has exactly
    `record_count` records; a `list`-kind has 1+ records each with
    a `/` terminator; an `array`-kind has N records closed by a
    block terminator (standalone `/` line).

    Attributes:
        items: The tokens making up this record's columns, in order.
            For an `array`-kind keyword, REPEAT_N_VALUE tokens
            contribute their `column_count` to the column index but
            only appear once in `items`.
        terminator: The TERMINATOR token (`/`) that closed this
            record, if any. The last record of a block-terminated
            array may have terminator=None.
        line: First line of the record (for diagnostics).
        column_count: Sum of column_count across items.
    """

    items: list[Token] = field(default_factory=list)
    terminator: Optional[Token] = None
    line: int = 0
    column_count: int = 0

    def column_count_total(self) -> int:
        """Sum of column_count across items (excluding the terminator)."""
        return sum(t.column_count for t in self.items)


@dataclass
class Keyword:
    """A single keyword occurrence in the deck.

    Attributes:
        name: The keyword's name (e.g. "WELSPECS").
        header_token: The KEYWORD token that started this keyword
            (the column-0 token after any leading blank/comment).
        records: The records parsed for this keyword.
        spec: The keyword's specification (resolved from the catalogue).
            None if the keyword is unknown.
        unknown_reason: For unknown keywords, the reason.
    """

    name: str
    header_token: Token
    records: list[Record] = field(default_factory=list)
    spec: Optional[object] = None  # KeywordSpec, but avoid circular import
    unknown_reason: Optional[str] = None

    def line(self) -> int:
        return self.header_token.line

    def record_count(self) -> int:
        return len(self.records)


@dataclass
class Section:
    """A section of the deck (RUNSPEC, GRID, etc.).

    Attributes:
        name: The section name.
        header_token: The SECTION_HEADER token.
        keywords: The keywords in this section, in order.
    """

    name: SectionName
    header_token: Token
    keywords: list[Keyword] = field(default_factory=list)

    def line(self) -> int:
        return self.header_token.line

    def keyword_names(self) -> list[str]:
        return [k.name for k in self.keywords]


@dataclass
class Deck:
    """The root AST node for a parsed deck.

    Attributes:
        source_file: The path to the .DATA file (None for ad-hoc text).
        sections: The 8 sections (some may be empty lists if the
            deck skipped them).
        include_depth: How deep this deck was included. 0 = top-level,
            1 = INCLUDE'd once, etc.
        parse_errors: Top-level parse errors (unknown keywords,
            section-order violations, etc.).
    """

    source_file: Optional[Path] = None
    sections: dict[SectionName, Section] = field(default_factory=dict)
    include_depth: int = 0
    parse_errors: list[str] = field(default_factory=list)

    def section(self, name: SectionName) -> Optional[Section]:
        return self.sections.get(name)

    def all_keywords(self) -> list[Keyword]:
        out: list[Keyword] = []
        for s in self.sections.values():
            out.extend(s.keywords)
        return out

    def keyword_count(self) -> int:
        return sum(len(s.keywords) for s in self.sections.values())