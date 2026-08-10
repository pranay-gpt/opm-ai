"""Section parser for the v2 linter.

Walks a Token stream (from tokenizer.py) and produces a Deck AST
(see ast.py). The parser enforces the 8-section canonical order and
dispatches each keyword by its SizeKind.

Algorithm (per token):
  1. If SECTION_HEADER: switch sections, validate order.
  2. If KEYWORD: look up spec, dispatch by size_kind:
     - none:  keyword alone, no records
     - fixed: collect exactly record_count records of item_count tokens
     - list:  collect 1+ records terminated by `/`
     - array: collect records of item_count tokens, block-terminated by
              a standalone `/` line
  3. Other tokens are value tokens; they belong to the current keyword
     based on context.

The parser is intentionally lenient on the trailing `/` of a record
(deferred terminator check, per OPM-ext `closeKw`). A `list`-kind
keyword's last record may be missing its `/` if the next token is a
SECTION_HEADER or EOL at column 0.

The parser is also lenient on out-of-section keywords. A keyword that
appears in the wrong section is recorded in `Deck.parse_errors` but
parsing continues (so we can report all errors at once).

Unknown keywords (not in the catalogue) are recorded as `Keyword` nodes
with `unknown_reason` set. They produce no records (we don't know the
schema).
"""

from __future__ import annotations

from typing import Iterator

from .ast import Deck, Keyword, Record, Section
from .catalogue import get_keyword
from .spec import KeywordSpec, SectionName, SizeKind
from .tokens import Token, TokenKind


# ---------------------------------------------------------------------------
# Parser entry points
# ---------------------------------------------------------------------------


def parse(tokens: list[Token]) -> Deck:
    """Parse a token stream into a Deck.

    Args:
        tokens: A list of tokens from the tokenizer (in order).

    Returns:
        A Deck AST with all sections, keywords, and records populated.
        Parse errors are accumulated in `Deck.parse_errors`.
    """
    deck = Deck()
    parser = _ParserState(deck, iter(tokens))
    parser.run()
    return parser.deck


def parse_file(text: str, source_file=None) -> Deck:
    """Convenience: tokenize and parse in one step."""
    from .tokenizer import tokenize_file

    tokens = tokenize_file(text, source_file=source_file)
    deck = parse(tokens)
    if source_file is not None:
        deck.source_file = source_file if not isinstance(source_file, str) else None
    return deck


# ---------------------------------------------------------------------------
# Parser state machine
# ---------------------------------------------------------------------------


class _ParserState:
    """Mutable parser state.

    Holds the current section, the current open keyword (if any), and
    the record being assembled. The Token stream is consumed via an
    iterator so backtracking is cheap (just call `next` again).
    """

    def __init__(self, deck: Deck, tokens: Iterator[Token]) -> None:
        self.deck = deck
        self._tokens = tokens
        self._current_section: Section | None = None
        self._current_keyword: Keyword | None = None
        self._current_record: Record | None = None

    def run(self) -> None:
        """Drive the state machine to completion."""
        for token in self._tokens:
            self._handle(token)

        # Final flush: if a record or keyword is still open, close it.
        self._close_record(force=True)
        self._close_keyword(force=True)

    # -- Token dispatch -----------------------------------------------------

    def _handle(self, token: Token) -> None:
        if token.kind == TokenKind.SECTION_HEADER:
            self._on_section_header(token)
        elif token.kind == TokenKind.KEYWORD:
            self._on_keyword(token)
        elif token.kind == TokenKind.EOL:
            self._on_eol(token)
        elif token.kind == TokenKind.COMMENT:
            # Comments never participate in parsing; ignore.
            pass
        elif token.kind == TokenKind.TERMINATOR:
            self._on_terminator(token)
        else:
            # Value token: append to current record.
            self._on_value(token)

    # -- Section handling ---------------------------------------------------

    def _on_section_header(self, token: Token) -> None:
        name = token.text
        if name not in SectionName.__members__:
            self.deck.parse_errors.append(
                f"{token.location_str()}: unknown section header '{name}'"
            )
            return
        section_name = SectionName(name)

        # Validate section order
        if self._current_section is not None:
            order = list(SectionName)
            current_idx = order.index(self._current_section.name)
            new_idx = order.index(section_name)
            if new_idx < current_idx:
                self.deck.parse_errors.append(
                    f"{token.location_str()}: section '{name}' appears "
                    f"after '{self._current_section.name.value}' "
                    f"(must be in canonical order)"
                )
                # Still allow re-entry (don't lose keywords)
            elif new_idx == current_idx:
                # Repeated section header (e.g. RUNSPEC RUNSPEC) — allow
                # but note. Some decks use this for visual separation.
                pass

        # Close any open keyword
        self._close_record(force=True)
        self._close_keyword(force=True)

        section = self.deck.sections.get(section_name)
        if section is None:
            section = Section(name=section_name, header_token=token)
            self.deck.sections[section_name] = section

        self._current_section = section

    # -- Keyword handling ---------------------------------------------------

    def _on_keyword(self, token: Token) -> None:
        name = token.text
        spec = get_keyword(name)

        # Close any open keyword
        self._close_record(force=True)
        self._close_keyword(force=True)

        kw = Keyword(name=name, header_token=token, spec=spec)
        if spec is None:
            kw.unknown_reason = f"unknown keyword '{name}'"
        else:
            # Section validity check
            if self._current_section is None:
                kw.unknown_reason = (
                    f"keyword '{name}' appears before any section header"
                )
            elif not spec.is_valid_in(self._current_section.name):
                kw.unknown_reason = (
                    f"keyword '{name}' is not valid in section "
                    f"'{self._current_section.name.value}'; "
                    f"valid sections: "
                    f"{[s.value for s in spec.sections]}"
                )

        if self._current_section is not None:
            self._current_section.keywords.append(kw)

        self._current_keyword = kw

        # size_kind=NONE: no records to collect, close immediately
        if spec is not None and spec.size_kind == SizeKind.NONE:
            self._close_keyword(force=True)

    def _on_eol(self, token: Token) -> None:
        # EOL closes a record only if the keyword is list/array.
        # For `fixed`, the record is closed by a terminator or by
        # reaching the item count.
        if self._current_keyword is None:
            return
        spec = self._current_keyword.spec
        if spec is None:
            return
        if spec.size_kind in (SizeKind.LIST, SizeKind.ARRAY):
            self._close_record(force=False)

    def _on_terminator(self, token: Token) -> None:
        if self._current_record is not None:
            self._current_record.terminator = token
            self._current_record.column_count = self._current_record.column_count_total()
            self._close_record(force=True)
        else:
            # Terminator without an open record: it's a block terminator
            # for an array-style keyword. Close the current keyword.
            self._close_keyword(force=True)

    def _on_value(self, token: Token) -> None:
        """A value token: append to the current record."""
        if self._current_keyword is None:
            # Value before any keyword — likely a parse error, but we
            # don't have a section to attach it to. Track in parse_errors.
            self.deck.parse_errors.append(
                f"{token.location_str()}: value token '{token.text}' "
                f"appears outside any keyword"
            )
            return
        if self._current_record is None:
            self._current_record = Record(line=token.line)
        self._current_record.items.append(token)

        # For FIXED keywords, close the record once we have item_count.
        spec = self._current_keyword.spec
        if spec is not None and spec.size_kind == SizeKind.FIXED:
            if (
                self._current_record.column_count_total()
                >= spec.item_count()
            ):
                # The FIXED record has all its columns. Wait for the
                # terminator to actually close it (deferred terminator).
                pass

    # -- Closing logic ------------------------------------------------------

    def _close_record(self, force: bool) -> None:
        """Close the current record and append it to the current keyword."""
        if self._current_record is None:
            return
        record = self._current_record
        # Decide if we should actually close
        spec = self._current_keyword.spec if self._current_keyword else None
        should_close = force or record.terminator is not None
        if not should_close and spec is not None:
            if spec.size_kind == SizeKind.FIXED:
                # FIXED closes on item count OR terminator
                should_close = record.column_count_total() >= spec.item_count()
        if not should_close:
            return

        if self._current_keyword is not None:
            self._current_keyword.records.append(record)
        self._current_record = None

    def _close_keyword(self, force: bool) -> None:
        """Close the current keyword."""
        if self._current_keyword is None:
            return
        kw = self._current_keyword
        spec = kw.spec
        # Final flush: append any in-progress record
        if self._current_record is not None:
            kw.records.append(self._current_record)
            self._current_record = None
        self._current_keyword = None
        # We don't return kw anywhere — it was already appended to a section.