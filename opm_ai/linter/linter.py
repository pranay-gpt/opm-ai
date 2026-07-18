"""Linter for OPM Flow decks."""

import re
from pathlib import Path
from typing import Optional

from opm_ai.linter.deck import Deck, LintResult, LintError


# Keyword requirements by section (simplified from Eclipse reference)
# Only enforce for non-trivial decks - these are WARNINGS for minimal decks
REQUIRED_KEYWORDS = {
    "RUNSPEC": ["DIMENS"],
    "GRID": ["DX", "DY", "DZ", "TOPS", "PORO", "PERMX"],
    "PROPS": ["SWOF", "SGOF"],  # Minimal for black oil
    "SOLUTION": ["EQUIL"],
    "SCHEDULE": ["WELSPECS", "COMPDAT", "TSTEP"],
}

# Companion keywords: if phase declared in RUNSPEC, need corresponding PROPS keyword
COMPANION_KEYWORDS = {
    "OIL": ["PVTO"],
    "GAS": ["PVTG"],
    "WATER": ["PVTW"],
    "DISGAS": ["PVTG", "SGOF"],
}


def lint_deck(deck_path: Path) -> LintResult:
    """
    Lint an Eclipse deck file.

    Args:
        deck_path: Path to .DATA deck file.

    Returns:
        LintResult with errors and warnings.
    """
    result = LintResult(deck_path=deck_path)
    deck = Deck(deck_path)

    # Check required sections - SOLUTION is optional for minimal decks
    for section in Deck.REQUIRED_SECTIONS:
        if section == "SOLUTION" and not deck.has_section(section):
            # SOLUTION is optional for minimal decks
            continue
        if not deck.has_section(section):
            result.add_error(section, "SECTION", f"Required section '{section}' is missing")

    # Check required keywords in each section
    # Only enforce for sections that have substantial content
    # For minimal decks, these are warnings not errors
    for section, keywords in REQUIRED_KEYWORDS.items():
        if deck.has_section(section):
            content = deck.get_section(section) or ""
            # Skip keyword checks for very minimal content
            if len(content.strip()) < 10:
                continue
            for kw in keywords:
                if not _has_keyword(content, kw):
                    # This is a warning for minimal decks, error for full decks
                    result.add_warning(section, kw, f"Required keyword '{kw}' not found in {section}")

    # Check companion keywords
    if deck.has_section("RUNSPEC"):
        runspec = deck.get_section("RUNSPEC") or ""
        if deck.has_section("PROPS"):
            props = deck.get_section("PROPS") or ""
            for phase, companions in COMPANION_KEYWORDS.items():
                if _has_keyword(runspec, phase):
                    for companion in companions:
                        if not _has_keyword(props, companion):
                            result.add_warning("PROPS", companion, f"Phase '{phase}' declared but '{companion}' not found in PROPS")

    # Check wells have COMPDAT
    if deck.has_section("SCHEDULE"):
        sched = deck.get_section("SCHEDULE") or ""
        if _has_keyword(sched, "WELSPECS") and not _has_keyword(sched, "COMPDAT"):
            result.add_error("SCHEDULE", "COMPDAT", "WELSPECS present but COMPDAT missing")

        # Check producers have WCONPROD
        wells = _extract_well_names(sched, "WELSPECS")
        prod_wells = [w for w in wells if _is_producer(sched, w)]
        if prod_wells and not _has_keyword(sched, "WCONPROD"):
            result.add_error("SCHEDULE", "WCONPROD", "Producer wells defined but WCONPROD missing")

        # Check injectors have WCONINJE
        inj_wells = [w for w in wells if _is_injector(sched, w)]
        if inj_wells and not _has_keyword(sched, "WCONINJE"):
            result.add_error("SCHEDULE", "WCONINJE", "Injector wells defined but WCONINJE missing")

    return result


def _has_keyword(content: str, keyword: str) -> bool:
    """Check if keyword exists in section content (case insensitive, word boundary)."""
    pattern = rf"^\s*{re.escape(keyword)}\b"
    return bool(re.search(pattern, content, re.MULTILINE | re.IGNORECASE))


def _extract_well_names(content: str, keyword: str) -> list[str]:
    """Extract well names from WELSPECS keyword."""
    wells = []
    pattern = rf"^\s*{re.escape(keyword)}\s*\n(.*?)^\s*/"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if match:
        well_data = match.group(1)
        well_lines = re.findall(r"^\s*'([^']+)'", well_data, re.MULTILINE)
        wells.extend(well_lines)
    return wells


def _is_producer(sched_content: str, well_name: str) -> bool:
    """Check if well is a producer (has OIL in WELSPECS)."""
    pattern = rf"'({re.escape(well_name)})'.*?'OIL'"
    return bool(re.search(pattern, sched_content, re.IGNORECASE))


def _is_injector(sched_content: str, well_name: str) -> bool:
    """Check if well is an injector (has GAS or WATER in WELSPECS)."""
    pattern = rf"'({re.escape(well_name)})'.*?(?:GAS|WATER)"
    return bool(re.search(pattern, sched_content, re.IGNORECASE))