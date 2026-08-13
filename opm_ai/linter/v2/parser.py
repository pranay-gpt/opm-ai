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

import re
from typing import Iterator, Optional

from .ast import Deck, Keyword, ParseError, Record, Section
from .catalogue import get_keyword
from .spec import CANONICAL_SECTIONS, KeywordSpec, SectionName, SizeKind
from .tokens import Token, TokenKind


# ---------------------------------------------------------------------------
# Parser entry points
# ---------------------------------------------------------------------------


def parse(tokens: list[Token], deck: Optional[Deck] = None) -> Deck:
    """Parse a token stream into a Deck.

    Args:
        tokens: A list of tokens from the tokenizer (in order).
        deck: Optional pre-constructed Deck to mutate. If None, a fresh
            Deck is created. Use `parse_file(..., source_file=...)`
            for the common case where you want source_file propagation.

    Returns:
        A Deck AST with all sections, keywords, and records populated.
        Parse errors are accumulated in `Deck.parse_errors`.
    """
    if deck is None:
        deck = Deck()
    parser = _ParserState(deck, iter(tokens))
    parser.run()
    return parser.deck


def parse_file(text: str, source_file=None) -> Deck:
    """Convenience: tokenize and parse in one step."""
    from .tokenizer import tokenize_file

    tokens = tokenize_file(text, source_file=source_file)
    # Set source_file on a pre-constructed deck so the parser can attach
    # it to ParseErrors emitted during parsing. Without this, L160
    # issues would have source_file=None even though we know it.
    deck = Deck(
        source_file=(
            Path(source_file) if isinstance(source_file, str) else source_file
        )
    )
    parsed = parse(tokens, deck=deck)
    # parse(tokens, deck=deck) mutates `deck` in place and returns it.
    return parsed


# ---------------------------------------------------------------------------
# Parser state machine
# ---------------------------------------------------------------------------

_FU_VAR_NAME_RE = re.compile(r"[FWGCRSU]U[_.0-9][A-Z0-9_.]*\Z")


def _classify_synthetic(name: str) -> "KeywordSpec | None":
    """Return the KeywordSpec for synthetic (unknown-token-as-keyword)
    constructs created on the fly. Returns None if the name doesn't
    match any known synthetic pattern.

    - FU_VAR_DECL covers FU_/WU_/GU_/CU_/RU_/SU_ flow-unit variable
      declarations at column 0 in SUMMARY.
    """
    if _FU_VAR_NAME_RE.match(name):
        from .catalogue.keywords import FU_DECL
        return FU_DECL
    return None


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
        # True once a TERMINATOR has been seen since the last
        # new-keyword header. Used to disambiguate "FU_* at column
        # 0 in SUMMARY starts a new keyword" from "FU_* is a
        # FUNVAR record item on the same line". When the previous
        # record was closed by `/`, the next column-0 word opens a
        # new keyword; otherwise it's a continuation item.
        self._last_was_terminator: bool = False

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
            # Smart dispatch: if the current keyword is a list/array
            # keyword whose first column is a free-form identifier
            # (well name, group, etc.) — marked by `first_column_is_name`
            # on the spec — treat the next KEYWORD token as the first
            # item of the next record rather than a new keyword. This
            # handles WELSPECS/COMPDAT/GCONPROD/GCONINJE/etc., where
            # every record starts with an identifier at column 0.
            #
            # Guards: for a *known* keyword (one with a catalogue
            # spec), only absorb into the current record if that spec
            # is NOT valid in the current section. This prevents
            # absorbing `WELSPECS` (valid in SCHEDULE) into a previous
            # `WELSPECS` record while still absorbing `FIELD` (valid
            # in RUNSPEC only) into a GCONPROD record in SCHEDULE.
            # Unknown tokens (well/group names) are always absorbed.
            #
            # Note: the dispatch fires regardless of `_last_was_terminator`
            # because some decks place records at column 0 without a
            # prior `/` terminator on the keyword header line (e.g.
            # GCONPROD immediately followed by `FIELD ORAT ... /` on
            # the next line). The section-validity guard alone is
            # sufficient to distinguish "new keyword block" from
            # "continuation record".
            if (
                token.text not in self.deck.sections
                and self._current_keyword is not None
                and self._current_keyword.spec is not None
                and self._current_keyword.spec.size_kind in
                    (SizeKind.LIST, SizeKind.ARRAY)
                and self._current_keyword.spec.first_column_is_name
            ):
                kw_spec = get_keyword(token.text)
                if (
                    kw_spec is None
                    or (
                        self._current_section is not None
                        and not kw_spec.is_valid_in(self._current_section.name)
                    )
                ):
                    self._on_value(token)
                    return
            self._on_keyword(token)
        elif token.kind == TokenKind.EOL:
            self._on_eol(token)
        elif token.kind == TokenKind.COMMENT:
            # Comments never participate in parsing; ignore.
            pass
        elif token.kind == TokenKind.TERMINATOR:
            self._on_terminator(token)
        elif token.kind == TokenKind.FU_VAR:
            # FU_* tokens at column 0 in the SUMMARY section are
            # flow-unit variable declarations (FU_VAR_DECL) — bare
            # markers with no record — when they appear either
            # between keywords (after a record-closing terminator) or
            # as the very first tokens in the section. The two cases
            # that distinguish them from values are:
            #   1. The current keyword has spec.size_kind==NONE (already
            #      closed) so any value would be a parse error.
            #   2. The last token was a terminator (new keyword starts).
            # In other contexts (FUNVAR record items, UDQ expression
            # variables, or as a continuation value after non-terminator
            # tokens), they are values.
            in_summary = (
                self._current_section is not None
                and self._current_section.name == SectionName.SUMMARY
                and token.col == 0
            )
            starts_new_keyword = (
                self._last_was_terminator
                or self._current_keyword is None
                or (
                    self._current_keyword.spec is not None
                    and self._current_keyword.spec.size_kind == SizeKind.NONE
                )
            )
            if in_summary and starts_new_keyword:
                self._on_unknown_keyword(token)
                return
            self._on_value(token)
        elif token.kind == TokenKind.UNKNOWN:
            # UNKNOWN tokens like "WOPR:W1" can appear in the SUMMARY
            # section as per-target summary variables. If we are in a
            # SUMMARY section (and no keyword is currently being built),
            # treat them as a new keyword whose name is the full token.
            if (
                ":" in token.text
                and self._current_section is not None
                and self._current_section.name == SectionName.SUMMARY
                and self._current_keyword is None
            ):
                self._on_unknown_keyword(token)
                return
            # Otherwise fall through to value handling.
            self._on_value(token)
        else:
            # Value token: append to current record.
            self._on_value(token)

    # -- Section handling ---------------------------------------------------

    def _on_unknown_keyword(self, token: Token) -> None:
        """Treat an UNKNOWN token as a new keyword (used for SUMMARY).

        FU_VAR_DECL keywords (FU_*, WU_*, GU_*, etc.) at column 0 are
        bare flow-unit declarations with no record. We attach the
        FU_VAR_DECL spec so the keyword is properly registered and
        the parser closes it immediately (size_kind=NONE).
        """
        name = token.text
        self._close_record(force=True)
        self._close_keyword(force=True)
        # Try to find a matching spec by name, or by synthetic pattern.
        spec = get_keyword(name) or _classify_synthetic(name)
        kw = Keyword(name=name, header_token=token, spec=spec)
        if spec is None:
            kw.unknown_reason = f"unknown keyword '{name}' (treated as synthetic)"
        if self._current_section is not None:
            kw.section = self._current_section
            self._current_section.keywords.append(kw)
        self._current_keyword = kw
        self._last_was_terminator = False
        # Apply NONE-size semantics: close immediately, so the next
        # bare column-0 token starts a new keyword.
        if spec is not None and spec.size_kind == SizeKind.NONE:
            self._close_keyword(force=True)

    def _on_section_header(self, token: Token) -> None:
        name = token.text
        if name not in SectionName.__members__ or name == "PRELUDE":
            self.deck.parse_errors.append(
                ParseError(
                    source_file=self.deck.source_file,
                    line=token.line,
                    col=token.col + 1,
                    message=f"unknown section header '{name}'",
                )
            )
            return
        section_name = SectionName(name)

        # Validate section order (PRELUDE can transition to any real section).
        if self._current_section is not None and self._current_section.name != SectionName.PRELUDE:
            order = list(CANONICAL_SECTIONS)
            try:
                current_idx = order.index(self._current_section.name)
                new_idx = order.index(section_name)
                if new_idx < current_idx:
                    self.deck.parse_errors.append(
                        ParseError(
                            source_file=self.deck.source_file,
                            line=token.line,
                            col=token.col + 1,
                            message=(
                                f"section '{name}' appears after "
                                f"'{self._current_section.name.value}' "
                                f"(must be in canonical order)"
                            ),
                        )
                    )
            except ValueError:
                pass

        # Close any open keyword
        self._close_record(force=True)
        self._close_keyword(force=True)
        self._last_was_terminator = False

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
        self._last_was_terminator = False

        kw = Keyword(name=name, header_token=token, spec=spec)
        if spec is None:
            kw.unknown_reason = f"unknown keyword '{name}'"
        else:
            # Section validity check
            if self._current_section is None:
                # No section yet — create a PRELUDE pseudo-section.
                from .tokens import TokenKind
                prelude_header = Token(
                    TokenKind.SECTION_HEADER, "PRELUDE", "PRELUDE",
                    token.line, 0, 7,
                    source_file=token.source_file,
                )
                prelude = Section(
                    name=SectionName.PRELUDE, header_token=prelude_header,
                )
                self.deck.sections[SectionName.PRELUDE] = prelude
                self._current_section = prelude
            elif not spec.is_valid_in(self._current_section.name):
                kw.unknown_reason = (
                    f"keyword '{name}' is not valid in section "
                    f"'{self._current_section.name.value}'; "
                    f"valid sections: "
                    f"{[s.value for s in spec.sections]}"
                )

        if self._current_section is not None:
            kw.section = self._current_section
            self._current_section.keywords.append(kw)

        self._current_keyword = kw

        # size_kind=NONE: no records to collect, close immediately
        if spec is not None and spec.size_kind == SizeKind.NONE:
            self._close_keyword(force=True)

    def _on_eol(self, token: Token) -> None:
        # EOL closes a record only if the keyword is list/array.
        # For `fixed`, the record is closed by a terminator or by
        # reaching the item count.
        # The terminator flag is NOT reset on EOL — it persists
        # until a non-EOL, non-terminator token arrives. This lets
        # us recognize column-0 words at the start of the *next*
        # line as new keywords when the previous line ended with
        # `/`. (EOLs are not "interesting" tokens in this respect.)
        if self._current_keyword is None:
            return
        spec = self._current_keyword.spec
        if spec is None:
            return
        if spec.size_kind in (SizeKind.LIST, SizeKind.ARRAY):
            self._close_record(force=False)

    def _on_terminator(self, token: Token) -> None:
        self._last_was_terminator = True
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
        # Any value clears the "last was terminator" state — the
        # record is now actively accumulating items.
        self._last_was_terminator = False
        if self._current_keyword is None:
            # Value before any keyword — likely a parse error, but we
            # don't have a section to attach it to. Track in parse_errors.
            self.deck.parse_errors.append(
                ParseError(
                    source_file=self.deck.source_file,
                    line=token.line,
                    col=token.col + 1,
                    message=(
                        f"value token '{token.text}' "
                        f"appears outside any keyword"
                    ),
                )
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