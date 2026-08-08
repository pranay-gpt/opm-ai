"""Deck parser for OPM Flow decks - hand-rolled section splitter."""

import enum
import re
from pathlib import Path
from typing import Iterator, Optional


class TokenType(enum.Enum):
    """Classification of a single deck token by lexical role.

    Used by the lexer (Phase 1 of the linter redesign) to distinguish OPM
    Flow keywords from user-defined summary variables. The catalogue
    scrape and L016 consult `_classify_token` to decide whether a token
    needs to be in the keyword catalogue at all.

    Phase 1 only adds USER_VARIABLE; KEYWORD is what the existing regex
    matched; OTHER is anything else (numbers, terminators, garbage).
    """

    KEYWORD = "keyword"
    USER_VARIABLE = "user_variable"
    OTHER = "other"


# User-defined variable prefix families observed in fixtures (OPM Flow UDQ
# convention). Tokens starting with any of these are recognised as user
# variables by the lexer and are exempt from catalogue membership checks.
# Other UDQ prefixes (TU_*, GI_*, WI_*, GU_*, AU_*) are intentionally NOT
# listed here: add them only when a real fixture demands it. Pre-emptive
# prefix expansion is the brute-force pattern the LinkedIn critique named.
_USER_VARIABLE_PREFIXES: tuple[str, ...] = ("FU_", "WU_")


class Deck:
    """Parsed Eclipse deck with section access.

    Hand-rolled section splitter that handles Eclipse/OPM deck quirks:
    - Section headers are case-insensitive word-boundary matches
    - Strips `--` comments when scanning for headers
    - Handles `/` terminators inside keywords (not section boundaries)
    - Preserves line numbers for error reporting
    """

    SECTION_HEADERS = [
        "RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS",
        "SOLUTION", "SUMMARY", "SCHEDULE", "ENDFIN"
    ]

    def __init__(self, deck_path: Path):
        """Parse deck file into sections.

        Args:
            deck_path: Path to the .DATA file
        """
        self.deck_path = deck_path
        self._sections: list[tuple[str, int, int, str]] = []  # (name, start_line, end_line, text)
        self._parse()

    def _parse(self) -> None:
        """Parse deck file into sections."""
        content = self.deck_path.read_text(encoding="utf-8", errors="replace")

        # Normalize line endings
        lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        # Build a comment-stripped version for header detection
        # We need to track original line numbers
        stripped_lines = []
        for i, line in enumerate(lines, 1):
            # Strip inline comments (-- to end of line)
            if "--" in line:
                # Only strip if -- is not inside a quoted string
                # Simple heuristic: count quotes before --
                before_comment = line.split("--")[0]
                if before_comment.count("'") % 2 == 0 and before_comment.count('"') % 2 == 0:
                    line = before_comment.rstrip()
            stripped_lines.append((i, line))

        # Find section headers (case-insensitive, word boundary, not in comment)
        section_pattern = re.compile(
            r"^\s*(" + "|".join(self.SECTION_HEADERS) + r")\b",
            re.IGNORECASE
        )

        matches = []
        for line_num, line in stripped_lines:
            match = section_pattern.match(line)
            if match:
                section_name = match.group(1).upper()
                matches.append((section_name, line_num))

        # Extract sections
        for i, (name, start_line) in enumerate(matches):
            end_line = matches[i + 1][1] - 1 if i + 1 < len(matches) else len(lines)
            # Get raw text from original lines (preserving everything)
            section_text = "\n".join(lines[start_line - 1:end_line]).rstrip()
            self._sections.append((name, start_line, end_line, section_text))

    @property
    def sections(self) -> list[str]:
        """List of section names in order of appearance."""
        return [s[0] for s in self._sections]

    def has_section(self, name: str) -> bool:
        """Check if section exists (case-insensitive)."""
        name_upper = name.upper()
        return any(section_name == name_upper for section_name, _, _, _ in self._sections)

    def get_section(self, name: str) -> Optional[str]:
        """Get raw section text by name (case-insensitive).

        Returns None if section not found.
        """
        name_upper = name.upper()
        for section_name, _, _, text in self._sections:
            if section_name == name_upper:
                return text
        return None

    def get_section_lines(self, name: str) -> Optional[tuple[int, int]]:
        """Get (start_line, end_line) for a section (1-indexed, inclusive)."""
        name_upper = name.upper()
        for section_name, start, end, _ in self._sections:
            if section_name == name_upper:
                return (start, end)
        return None

    # ------------------------------------------------------------------ #
    # Phase 1 — Token classification                                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _classify_token(token: str) -> TokenType:
        """Classify a single deck token by lexical role.

        Pure function: same input -> same output. Safe to call from the
        catalogue scrape (off-process) and from rules (in-process). The
        input is whatever the linter would normally regex-match as a
        keyword (already uppercased by the caller for consistency, but
        the function uppercases defensively).

        Phase 1 distinguishes USER_VARIABLE (`FU_*`, `WU_*`) from KEYWORD
        so L016 and the catalogue scrape can ignore user-defined summary
        mnemonics. KEYWORD is the default for any uppercase alpha-led
        token; OTHER covers numerics, terminators, and anything that does
        not look like an OPM Flow identifier.

        The user-variable prefix list is intentionally narrow. Add to
        `_USER_VARIABLE_PREFIXES` only when a real fixture or student
        deck demonstrates the need; pre-emptive expansion is exactly the
        brute-force pattern the LinkedIn critique named.
        """
        upper = token.upper()
        if not upper or not upper[0].isalpha():
            return TokenType.OTHER
        if any(upper.startswith(p) for p in _USER_VARIABLE_PREFIXES):
            return TokenType.USER_VARIABLE
        if re.match(r"^[A-Z][A-Z0-9_]*$", upper):
            return TokenType.KEYWORD
        return TokenType.OTHER

    def iter_keywords(
        self, *, section: Optional[str] = None
    ) -> Iterator[tuple[str, int, TokenType]]:
        """Yield (token, line_number, token_type) for KEYWORD and
        USER_VARIABLE tokens across the deck (or one section).

        Phase 1 typed-iterator replacement for the per-rule regex scan in
        L016 and the catalogue scrape. Existing rules that still use
        `_KEYWORD_LINE_RE` (e.g. L001, L013, L014) keep their current
        regex; this iterator is the new entry point for the *membership
        check* layer only.

        Line numbers are 1-indexed, deck-wide (i.e., they match what the
        existing `get_section_lines()` returns, not section-relative).

        Args:
            section: If given, restrict iteration to that section name
                (case-insensitive). If None, iterate over every section
                in order.
        """
        for section_name in self.sections:
            if section is not None and section_name.upper() != section.upper():
                continue
            text = self.get_section(section_name)
            if not text:
                continue
            section_line_range = self.get_section_lines(section_name)
            base_line = section_line_range[0] if section_line_range else 1
            for offset, line in enumerate(text.split("\n")):
                stripped = line.strip()
                if not stripped or stripped.startswith("--"):
                    continue
                m = re.match(
                    r"^([A-Z][A-Z0-9_]*)\s*(?:--.*)?$",
                    stripped,
                    re.IGNORECASE,
                )
                if not m:
                    continue
                token_upper = m.group(1).upper()
                token_type = self._classify_token(token_upper)
                if token_type is TokenType.OTHER:
                    continue
                yield token_upper, base_line + offset, token_type

    def __repr__(self) -> str:
        return f"Deck({self.deck_path}, sections={self.sections})"