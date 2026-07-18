"""Deck parser for OPM Flow decks - hand-rolled section splitter."""

import re
from pathlib import Path
from typing import Optional


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

    def __repr__(self) -> str:
        return f"Deck({self.deck_path}, sections={self.sections})"