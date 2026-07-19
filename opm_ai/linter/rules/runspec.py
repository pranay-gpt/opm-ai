"""RUNSPEC section lint rules - L002, L015."""

import re
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue


def _has_keyword(section_text: str, keyword: str) -> bool:
    """Check if keyword exists in section."""
    pattern = rf"(?im)^\s*{re.escape(keyword)}\b"
    return bool(re.search(pattern, section_text))


def rule_L002_phase_mismatch(deck: Deck) -> list[LintIssue]:
    """L002: Phase declared in RUNSPEC but missing companion PROPS keyword (ERROR).

    OIL -> PVTO, GAS -> PVTG, WATER -> PVTW, DISGAS -> PVTG/SGOF, VAPOIL -> PVDO/SWOF
    """
    issues = []

    runspec = deck.get_section("RUNSPEC")
    props = deck.get_section("PROPS")

    if not runspec or not props:
        return issues

    # Phase -> required PROPS keywords
    phase_requirements = {
        "OIL": ["PVTO", "SWOF"],
        "GAS": ["PVTG", "SGOF"],
        "WATER": ["PVTW"],
        "DISGAS": ["PVTG", "SGOF"],
        "VAPOIL": ["PVDO", "SWOF"],
    }

    for phase, required_keywords in phase_requirements.items():
        if _has_keyword(runspec, phase):
            for req_kw in required_keywords:
                if not _has_keyword(props, req_kw):
                    props_lines = deck.get_section_lines("PROPS")
                    line_num = props_lines[0] if props_lines else None
                    issues.append(LintIssue(
                        severity="ERROR",
                        section="PROPS",
                        keyword=req_kw,
                        line=line_num,
                        message=f"Phase '{phase}' declared in RUNSPEC but '{req_kw}' not found in PROPS",
                        rule_id="L002"
                    ))

    return issues


def rule_L015_missing_dimens(deck: Deck) -> list[LintIssue]:
    """L015: Missing DIMENS in RUNSPEC (ERROR).

    Skipped when RUNSPEC contains INCLUDE - DIMENS may live in the included
    file, which the v1 linter does not resolve.
    """
    issues = []

    runspec = deck.get_section("RUNSPEC")
    if not runspec:
        return issues

    if _has_keyword(runspec, "INCLUDE"):
        return issues

    if not _has_keyword(runspec, "DIMENS"):
        runspec_lines = deck.get_section_lines("RUNSPEC")
        line_num = runspec_lines[0] if runspec_lines else None
        issues.append(LintIssue(
            severity="ERROR",
            section="RUNSPEC",
            keyword="DIMENS",
            line=line_num,
            message="RUNSPEC must contain DIMENS keyword",
            rule_id="L015"
        ))

    return issues