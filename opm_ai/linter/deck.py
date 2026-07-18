"""Deck parser and lint result types for OPM Flow decks."""

import re
from pathlib import Path
from typing import Optional


class LintError:
    """Single lint error."""

    def __init__(self, section: str, keyword: str, message: str, line: int | None = None):
        self.section = section
        self.keyword = keyword
        self.message = message
        self.line = line

    def __str__(self) -> str:
        loc = f" (line {self.line})" if self.line else ""
        return f"[{self.section}] {self.keyword}: {self.message}{loc}"


class LintResult:
    """Result of linting a deck."""

    def __init__(self, deck_path: Path):
        self.deck_path = str(deck_path)
        self.errors: list[LintError] = []
        self.warnings: list[LintError] = []

    @property
    def passed(self) -> bool:
        """True if no errors."""
        return len(self.errors) == 0

    def add_error(self, section: str, keyword: str, message: str, line: int | None = None) -> None:
        """Add an error."""
        self.errors.append(LintError(section, keyword, message, line))

    def add_warning(self, section: str, keyword: str, message: str, line: int | None = None) -> None:
        """Add a warning."""
        self.warnings.append(LintError(section, keyword, message, line))

    def __str__(self) -> str:
        if self.passed:
            return f"LintResult({self.deck_path}: Passed)"
        return f"LintResult({self.deck_path}: {len(self.errors)} errors, {len(self.warnings)} warnings)"


class Deck:
    """Parsed Eclipse deck with section access."""

    # Required sections for a valid deck
    REQUIRED_SECTIONS = [
        "RUNSPEC",
        "GRID",
        "PROPS",
        "SOLUTION",
        "SCHEDULE",
    ]

    def __init__(self, deck_path: Path):
        """Parse deck file into sections."""
        self.deck_path = deck_path
        self.sections: dict[str, str] = {}
        self._parse()

    def _parse(self) -> None:
        """Parse deck file into sections."""
        content = self.deck_path.read_text()

        # Find all section headers
        section_headers = [
            "RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS",
            "SOLUTION", "SUMMARY", "SCHEDULE"
        ]

        pattern = re.compile(
            r"^\s*(" + "|".join(section_headers) + r")\s*$",
            re.MULTILINE | re.IGNORECASE,
        )

        matches = list(pattern.finditer(content))
        for i, match in enumerate(matches):
            section_name = match.group(1).upper()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            self.sections[section_name] = content[start:end].strip()

    def get_section(self, name: str) -> Optional[str]:
        """Get section content by name (case insensitive)."""
        return self.sections.get(name.upper())

    def has_section(self, name: str) -> bool:
        """Check if section exists."""
        return name.upper() in self.sections

    def __repr__(self) -> str:
        return f"Deck({self.deck_path}, sections={list(self.sections.keys())})"