"""SOLUTION and SUMMARY section lint rules - L009, L010."""

from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue


def _has_keyword(section_text: str, keyword: str) -> bool:
    """Check if keyword exists in section."""
    import re
    pattern = rf"(?im)^\s*{re.escape(keyword)}\b"
    return bool(re.search(pattern, section_text))


def rule_L009_missing_solution(deck: Deck) -> list[LintIssue]:
    """L009: Missing SOLUTION section and no RESTART (WARNING).

    SOLUTION is WARNING only because Flow can use default equilibration.
    But ERROR if EQUIL or RPTRST suggests equilibrium initialization expected.
    """
    issues = []

    solution = deck.get_section("SOLUTION")
    if solution:
        return issues  # SOLUTION present, no issue

    # Check if deck has EQUIL or RPTRST anywhere (indicates equilibrium init expected)
    has_equil_keyword = False
    for section_name in deck.sections:
        sec_text = deck.get_section(section_name)
        if sec_text and (_has_keyword(sec_text, "EQUIL") or _has_keyword(sec_text, "RPTRST")):
            has_equil_keyword = True
            break

    # Also check SOLUTION keyword in other sections (some decks put EQUIL in SOLUTION)
    # But we already know SOLUTION section is missing

    severity = "ERROR" if has_equil_keyword else "WARNING"
    message = "Missing SOLUTION section; Flow will use default equilibration"
    if has_equil_keyword:
        message = "Missing SOLUTION section but EQUIL/RPTRST present - equilibrium initialization expected"

    issues.append(LintIssue(
        severity=severity,
        section="SOLUTION",
        keyword="SOLUTION",
        line=None,
        message=message,
        rule_id="L009"
    ))

    return issues


def rule_L010_missing_summary(deck: Deck) -> list[LintIssue]:
    """L010: No SUMMARY section (WARNING).

    SUMMARY is always WARNING because deck runs without it (just no time-series output).
    """
    issues = []

    summary = deck.get_section("SUMMARY")
    if not summary:
        issues.append(LintIssue(
            severity="WARNING",
            section="SUMMARY",
            keyword="SUMMARY",
            line=None,
            message="No SUMMARY section; no time-series output will be written",
            rule_id="L010"
        ))

    return issues