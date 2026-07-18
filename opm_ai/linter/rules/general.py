"""General lint rules - L001, L013, L014."""

import re
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue

# Section headers that should NOT be flagged as missing terminators
SECTION_HEADERS = frozenset({
    "RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS",
    "SOLUTION", "SUMMARY", "SCHEDULE", "ENDFIN"
})

# Keywords that don't require terminators (simple flag keywords)
NO_TERMINATOR_KEYWORDS = frozenset({
    "ENDFIN", "END", "NOECHO", "ECHO",
    # Simple flag keywords (no data, just flags)
    "OIL", "GAS", "WATER", "DISGAS", "VAPOIL",
    "FIELD", "METRIC", "LAB",
    "UNIFIN", "UNIFOUT",
    "INIT", "COORD", "ZCORN", "NTG",
    "SWOF", "SGOF", "SLGOF", "PVDO", "PVTG", "PVTO", "PVTW",
    "ROCK", "PVDG", "PVDO",
    "EQLDIMS", "TABDIMS", "WELLDIMS",
    "START", "TITLE",
    "EQLNUM", "FIPNUM", "PVTNUM", "SATNUM", "ROCKNUM",
    "PRESSURE", "SGAS", "SOIL", "SWAT", "RS", "RV", "EQUIL",
    "WELSPECS", "COMPDAT", "WCONPROD", "WCONINJE",
    "WCONHIST", "GCONPROD", "GCONINJE", "TSTEP", "DATES",
    "DENSITY", "PVCDO", "PVCGW", "PVCO",
    "FOPR", "FGOR", "FOPT", "FWPT", "FGPT", "FWIR", "FGIR",
    "END",
})


def _line_terminates(stripped: str) -> bool:
    """True if the line contains a record terminator '/'.

    Eclipse ignores everything after '/' on a line, so
    `8300.0 1.270 / RS VS DEPTH` IS terminated. Quoted strings (well names,
    INCLUDE paths) are removed first so a '/' inside them does not count,
    and inline '--' comments are cut before checking.
    """
    unquoted = re.sub(r"'[^']*'", "", stripped)
    unquoted = unquoted.split("--")[0]
    return "/" in unquoted


def rule_L001_missing_terminator(deck: Deck) -> list[LintIssue]:
    """L001: Missing terminating '/' on keyword (ERROR).

    Scans each section for keywords that don't end with '/' before next keyword or section.
    The SUMMARY section is exempt: its mnemonics (FGPR, ALL, RUNSUM, ...) are
    bare flags or self-terminating and Flow accepts them without '/'.
    """
    issues = []

    for section_name in deck.sections:
        if section_name.upper() == "SUMMARY":
            continue

        text = deck.get_section(section_name)
        if not text:
            continue

        lines = text.split("\n")
        current_keyword = None
        keyword_start_line = None

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("--"):
                continue

            # Check if line contains a record terminator
            if _line_terminates(stripped):
                # This line terminates the current keyword
                current_keyword = None
                keyword_start_line = None
                continue

            # TITLE takes exactly one line of free text (no terminator);
            # consume it so a title like "SPE 9" is not mistaken for a keyword.
            if current_keyword == "TITLE":
                current_keyword = None
                keyword_start_line = None
                continue

            # Check if this looks like a new keyword (uppercase word at start of line)
            kw_match = re.match(r"^([A-Z][A-Z0-9_]*)\b", stripped)
            if kw_match:
                # If we had a previous keyword without terminator, flag it
                if current_keyword and current_keyword not in NO_TERMINATOR_KEYWORDS:
                    # Also skip section headers
                    if current_keyword not in SECTION_HEADERS:
                        # Find the line number in the original deck
                        section_lines = deck.get_section_lines(section_name)
                        if section_lines:
                            start_line, _ = section_lines
                            actual_line = start_line + keyword_start_line - 1
                            issues.append(LintIssue(
                                severity="ERROR",
                                section=section_name,
                                keyword=current_keyword,
                                line=actual_line,
                                message=f"Keyword '{current_keyword}' is missing terminating '/'",
                                rule_id="L001"
                            ))
                current_keyword = kw_match.group(1)
                keyword_start_line = i

        # Check last keyword in section
        if current_keyword and current_keyword not in NO_TERMINATOR_KEYWORDS:
            if current_keyword not in SECTION_HEADERS:
                section_lines = deck.get_section_lines(section_name)
                if section_lines:
                    start_line, _ = section_lines
                    actual_line = start_line + keyword_start_line - 1
                    issues.append(LintIssue(
                        severity="ERROR",
                        section=section_name,
                        keyword=current_keyword,
                        line=actual_line,
                        message=f"Keyword '{current_keyword}' is missing terminating '/'",
                        rule_id="L001"
                    ))

    return issues


def rule_L013_keyword_order(deck: Deck) -> list[LintIssue]:
    """L013: Keyword not in canonical Eclipse order within section (INFO).

    This is a style check - keywords should follow recommended ordering.
    """
    issues = []
    # Canonical order for each section (subset of common keywords)
    canonical_order = {
        "RUNSPEC": [
            "TITLE", "START", "DIMENS", "EQLDIMS", "TABDIMS",
            "OIL", "GAS", "WATER", "DISGAS", "VAPOIL",
            "FIELD", "METRIC", "LAB", "WELLDIMS", "UNIFIN", "UNIFOUT"
        ],
        "GRID": [
            "INIT", "DX", "DY", "DZ", "TOPS", "PORO",
            "PERMX", "PERMY", "PERMZ", "NTG", "COORD", "ZCORN"
        ],
        "PROPS": [
            "SWOF", "SGOF", "SLGOF", "PVDO", "PVTG", "PVTO", "PVTW",
            "ROCK", "PVCDO", "PVCGW", "PVCO", "SATNUM", "PVTNUM", "ROCKNUM"
        ],
        "REGIONS": [
            "EQLNUM", "FIPNUM", "PVTNUM", "SATNUM", "ROCKNUM"
        ],
        "SOLUTION": [
            "PRESSURE", "SGAS", "SOIL", "SWAT", "RS", "RV", "EQUIL"
        ],
        "SUMMARY": [
            "WELSPECS", "COMPDAT", "ALL"
        ],
        "SCHEDULE": [
            "WELSPECS", "COMPDAT", "WCONPROD", "WCONINJE",
            "WCONHIST", "GCONPROD", "GCONINJE", "TSTEP", "DATES"
        ],
    }

    for section_name in deck.sections:
        if section_name not in canonical_order:
            continue

        text = deck.get_section(section_name)
        if not text:
            continue

        # Extract keywords in order of appearance
        found_keywords = []
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            kw_match = re.match(r"^([A-Z][A-Z0-9_]*)\b", stripped)
            if kw_match:
                kw = kw_match.group(1)
                if kw not in ("/", "ENDFIN"):
                    found_keywords.append(kw)

        # Check order against canonical
        expected_order = {kw: i for i, kw in enumerate(canonical_order[section_name])}
        last_order = -1
        for kw in found_keywords:
            if kw in expected_order:
                order = expected_order[kw]
                if order < last_order:
                    section_lines = deck.get_section_lines(section_name)
                    line_num = None
                    if section_lines:
                        start_line, _ = section_lines
                        # Approximate line
                        line_num = start_line + found_keywords.index(kw)
                    issues.append(LintIssue(
                        severity="INFO",
                        section=section_name,
                        keyword=kw,
                        line=line_num,
                        message=f"Keyword '{kw}' appears out of recommended order",
                        rule_id="L013"
                    ))
                last_order = max(last_order, order)

    return issues


def rule_L014_include_depth(deck: Deck) -> list[LintIssue]:
    """L014: INCLUDE depth > 2 or absolute path (INFO)."""
    issues = []

    for section_name in deck.sections:
        text = deck.get_section(section_name)
        if not text:
            continue

        for i, line in enumerate(text.split("\n"), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue

            # Check for INCLUDE keyword
            if stripped.upper().startswith("INCLUDE"):
                # Extract path
                parts = stripped.split()
                if len(parts) >= 2:
                    path = parts[1].strip("'\"")
                    # Check for absolute path
                    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
                        section_lines = deck.get_section_lines(section_name)
                        line_num = None
                        if section_lines:
                            line_num = section_lines[0] + i - 1
                        issues.append(LintIssue(
                            severity="INFO",
                            section=section_name,
                            keyword="INCLUDE",
                            line=line_num,
                            message=f"INCLUDE uses absolute path: {path}",
                            rule_id="L014"
                        ))
                    # Check depth
                    depth = path.count("/") + path.count("\\")
                    if depth > 2:
                        section_lines = deck.get_section_lines(section_name)
                        line_num = None
                        if section_lines:
                            line_num = section_lines[0] + i - 1
                        issues.append(LintIssue(
                            severity="INFO",
                            section=section_name,
                            keyword="INCLUDE",
                            line=line_num,
                            message=f"INCLUDE path depth > 2: {path}",
                            rule_id="L014"
                        ))

    return issues