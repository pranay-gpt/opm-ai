"""PROPS section lint rules - L005, L012."""

import re
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue


def _has_keyword(section_text: str, keyword: str) -> bool:
    """Check if keyword exists in section."""
    pattern = rf"(?im)^\s*{re.escape(keyword)}\b"
    return bool(re.search(pattern, section_text))


def _get_keyword_values(section_text: str, keyword: str) -> list[float]:
    """Extract all values for a keyword as floats."""
    values = []
    pattern = rf"(?is)^\s*{re.escape(keyword)}\b\s*(.*?)(?=^\s*[A-Z][A-Z0-9_]*\b|^\s*--|$)"
    match = re.search(pattern, section_text, re.MULTILINE | re.DOTALL)
    if match:
        content = match.group(1)
        tokens = content.split()
        for token in tokens:
            if token != "/":
                try:
                    values.append(float(token))
                except ValueError:
                    pass
    return values


def rule_L005_pvt_phase_mismatch(deck: Deck) -> list[LintIssue]:
    """L005: Phase declared in RUNSPEC but missing companion PROPS keyword (ERROR).

    OIL -> PVTO, SWOF
    GAS -> PVTG, SGOF
    WATER -> PVTW
    DISGAS -> PVTG, SGOF
    """
    issues = []

    runspec = deck.get_section("RUNSPEC")
    props = deck.get_section("PROPS")

    if not runspec or not props:
        return issues

    phase_requirements = {
        "OIL": ["PVTO", "SWOF"],
        "GAS": [["PVTG", "PVDG"], "SGOF"],  # PVTG or PVDG acceptable
        "WATER": ["PVTW"],
        "DISGAS": [["PVTG", "PVDG"], "SGOF"],  # PVTG or PVDG acceptable
        "VAPOIL": ["PVDO", "SWOF"],
    }

    for phase, required_keywords in phase_requirements.items():
        if _has_keyword(runspec, phase):
            for req_kw in required_keywords:
                # Handle alternative keywords (list means OR)
                if isinstance(req_kw, list):
                    # Need at least one of the alternatives
                    if not any(_has_keyword(props, alt) for alt in req_kw):
                        props_lines = deck.get_section_lines("PROPS")
                        line_num = props_lines[0] if props_lines else None
                        issues.append(LintIssue(
                            severity="ERROR",
                            section="PROPS",
                            keyword="/".join(req_kw),
                            line=line_num,
                            message=f"Phase '{phase}' declared in RUNSPEC but none of {req_kw} found in PROPS",
                            rule_id="L005"
                        ))
                else:
                    if not _has_keyword(props, req_kw):
                        props_lines = deck.get_section_lines("PROPS")
                        line_num = props_lines[0] if props_lines else None
                        issues.append(LintIssue(
                            severity="ERROR",
                            section="PROPS",
                            keyword=req_kw,
                            line=line_num,
                            message=f"Phase '{phase}' declared in RUNSPEC but '{req_kw}' not found in PROPS",
                            rule_id="L005"
                        ))

    return issues


def rule_L012_sat_endpoint_consistency(deck: Deck) -> list[LintIssue]:
    """L012: SWOF/SGOF endpoints inconsistent with SATNUM regions (WARNING).

    Checks if saturation table endpoints (SWL, SGL) are consistent with
    region assignments. Simplified check - warns if tables exist but
    SATNUM regions reference tables beyond available.
    """
    issues = []

    props = deck.get_section("PROPS")
    regions = deck.get_section("REGIONS")

    if not props or not regions:
        return issues

    # Check if SATNUM exists in REGIONS
    if not _has_keyword(regions, "SATNUM"):
        return issues

    # Get SATNUM values
    satnum_values = _get_keyword_values(regions, "SATNUM")
    max_satnum = max([int(v) for v in satnum_values if v.isdigit()], default=0)

    # Check number of SWOF tables
    swof_count = 0
    lines = props.split("\n")
    for line in lines:
        if line.strip().upper().startswith("SWOF"):
            swof_count += 1

    if max_satnum > swof_count:
        props_lines = deck.get_section_lines("PROPS")
        line_num = props_lines[0] if props_lines else None
        issues.append(LintIssue(
            severity="WARNING",
            section="PROPS",
            keyword="SWOF",
            line=line_num,
            message=f"SATNUM region {max_satnum} references table beyond {swof_count} SWOF tables",
            rule_id="L012"
        ))

    return issues