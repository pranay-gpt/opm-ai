"""Classify a deck into one of 8 fixture categories.

The categories drive the linter's test coverage matrix. They are not
mutually exclusive at the keyword level — a deck can be in 'spe' AND
'udq-actionx' if it has both. The classifier returns the *primary*
category plus any *secondary* tags.

Categories (8):
  1. minimal    — hand-written or stripped-down, no INCLUDE, no EDIT
  2. spe        — SPE1/3/5/9 reference decks (opm-simulation-reference)
  3. include    — uses INCLUDE keyword
  4. edit       — uses EQUALS/COPY/MULTIPLY/OPERATE action operands
  5. udq        — uses UDQ DEFINE/ASSIGN/UPDATE/UNITS or ACTIONX
  6. repeat     — uses n*value repetition syntax in a non-trivial way
  7. region     — uses FIPNUM/REGIONS/MULTIREG/EQUALREG
  8. action     — uses ACTIONX/PYACTION blocks (action keywords)

The primary category is the *first* match in this order. Secondary
categories are the rest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


CATEGORIES = (
    "minimal",
    "spe",
    "include",
    "edit",
    "udq",
    "repeat",
    "region",
    "action",
)


@dataclass
class Classification:
    """A deck's category tags."""

    primary: str
    secondary: list[str] = field(default_factory=list)
    signals: dict[str, list[str]] = field(default_factory=dict)

    def matches(self, category: str) -> bool:
        return self.primary == category or category in self.secondary


# Regex patterns for category detection. Match is case-insensitive for the
# keyword-name patterns (INCLUDE, FIPNUM, etc.) but case-sensitive for
# the FU/WU variable pattern — these are upper-case identifiers in a
# mixed-case deck and we must not match every keyword starting with the
# right letters.
_PATTERNS: dict[str, re.Pattern[str]] = {
    # INCLUDE / IMPORT: a token of these names on its own line
    "include": re.compile(r"^\s*(INCLUDE|IMPORT)\b", re.IGNORECASE | re.MULTILINE),
    # EQUALS / COPY / MULTIPLY / OPERATE / EQUALREG / MULTIREG / ADDREG
    # (EQUALREG and MULTIREG are also region markers, handled below)
    "edit": re.compile(
        r"^\s*(EQUALS|COPY|MULTIPLY|OPERATE|ADDREG|OPERATER|MULTIREG|EQUALREG)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    # UDQ control words (these are at the *start* of a UDQ statement)
    "udq_stmt": re.compile(
        r"^\s*(UDQ|UDT)\b", re.IGNORECASE | re.MULTILINE
    ),
    # FU_* / WU_* / RU_* etc.: a complete token, not part of a keyword.
    # The OPM extension's regex is `^[ABCFGRSW]U[A-Z0-9_]+$` applied to
    # a single token. In our full-text context, we require:
    #   - a non-letter/digit/underscore before the match (lookbehind)
    #   - a digit or underscore right after the scope letter U
    #     (excludes RUNSPEC, WATER, WUMVAR — none have a digit/underscore
    #     in the U position)
    # Case-sensitive: FU_MYVAR is upper, but generic keywords like
    # INCLUDE or Water should not match.
    "fu_var": re.compile(r"(?<![A-Z0-9_])[ABCFGRSW]U[_0-9][A-Z0-9_]*"),
    # n*value: an integer followed by '*' IMMEDIATELY followed by a
    # number (no whitespace). The OPM extension tokenises `N*` and
    # `N*value` as two different kinds; the latter is the "repeat"
    # syntax where N is the count and `value` is the repeated value.
    # We match `N*value` only (not bare `N*` which is a default).
    "repeat": re.compile(r"\b\d+\*[-+]?\d"),
    # FIPNUM (REGIONS is a section header, less specific)
    "region": re.compile(r"^\s*FIPNUM\b", re.IGNORECASE | re.MULTILINE),
    # ACTIONX / PYACTION
    "action": re.compile(
        r"^\s*(ACTIONX|PYACTION)\b", re.IGNORECASE | re.MULTILINE
    ),
}


# Path patterns for the 'spe' category. These are the OPM-Flow reference
# decks distributed as `tests/fixtures/spe{1,3,5,9}/...`. The path must
# contain a `/speN/` segment (or start with `speN/`).
_SPE_PATH_RE = re.compile(r"(?:^|/)spe[1-9](?:/|$)")


def _read_text(path: Path, max_bytes: int = 256_000) -> str:
    """Read a deck as text, truncated to max_bytes (most decks are small)."""
    try:
        return path.read_text(errors="replace")[:max_bytes]
    except Exception:
        return ""


def _detect_signals(text: str) -> dict[str, list[str]]:
    """Detect which category signals appear in the deck.

    Returns a dict mapping signal name -> first few matching lines.
    """
    signals: dict[str, list[str]] = {}
    for name, pattern in _PATTERNS.items():
        matches: list[str] = []
        for m in pattern.finditer(text):
            # Capture a short context window for diagnostic purposes
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 60)
            snippet = text[start:end].replace("\n", "\\n").strip()
            matches.append(snippet)
            if len(matches) >= 3:
                break
        if matches:
            signals[name] = matches
    return signals


def classify_deck(path: Path) -> Classification:
    """Classify a deck into one of the 8 categories.

    Args:
        path: Path to the .DATA file.

    Returns:
        Classification with primary category, secondary categories, and
        signal evidence.
    """
    text = _read_text(path)
    signals = _detect_signals(text)

    # Compute which categories this deck belongs to
    tags: list[str] = []
    if signals.get("include"):
        tags.append("include")
    if signals.get("edit"):
        tags.append("edit")
    if signals.get("udq_stmt") or signals.get("fu_var"):
        tags.append("udq")
    if signals.get("repeat"):
        tags.append("repeat")
    if signals.get("region"):
        tags.append("region")
    if signals.get("action"):
        tags.append("action")

    # Special: SPE by path
    rel = path.as_posix()
    if _SPE_PATH_RE.search(rel):
        tags.append("spe")

    # Primary: the *first* matching tag in canonical order
    primary = "minimal"
    for cat in CATEGORIES:
        if cat in tags:
            primary = cat
            break

    # Everything else is secondary
    secondary = [t for t in tags if t != primary]

    return Classification(primary=primary, secondary=secondary, signals=signals)


def classify_corpus(paths: list[Path]) -> dict[Path, Classification]:
    """Classify every deck in a corpus.

    Args:
        paths: List of deck paths.

    Returns:
        Dict mapping path -> Classification.
    """
    return {p: classify_deck(p) for p in paths}
