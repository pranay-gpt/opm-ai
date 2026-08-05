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

    # Phase -> required PROPS keywords. Each phase must have AT LEAST ONE
    # keyword from each group. GAS/DISGAS accept either PVTG (rich/wet
    # gas with vaporized oil) or PVDG (dry gas); the builder emits PVDG
    # for the default depletion scenario. VAPOIL accepts either PVDO
    # (default) or PVTG (used in SPE3-style compositional decks).
    # Relperm tables come in two families: family I (SWOF/SGOF) and
    # family II (SWFN/SGFN). OIL accepts either SWOF or SGOF (Flow
    # runs OIL+GAS decks with only SGOF as the oil relperm); GAS
    # requires SGOF or SGFN; VAPOIL requires SWOF or SWFN.
    phase_requirements: dict[str, list[list[str]]] = {
        "OIL": [["PVTO"], ["SWOF", "SGOF"]],
        "GAS": [["PVTG", "PVDG"], ["SGOF", "SGFN"]],
        "WATER": [["PVTW"]],
        "DISGAS": [["PVTG", "PVDG"], ["SGOF", "SGFN"]],
        "VAPOIL": [["PVDO", "PVTG"], ["SWOF", "SWFN"]],
    }

    for phase, groups in phase_requirements.items():
        if not _has_keyword(runspec, phase):
            continue
        for group in groups:
            if any(_has_keyword(props, kw) for kw in group):
                continue
            # none of the alternatives in this group were present
            props_lines = deck.get_section_lines("PROPS")
            line_num = props_lines[0] if props_lines else None
            missing = " or ".join(group)
            issues.append(LintIssue(
                severity="ERROR",
                section="PROPS",
                keyword=phase,
                line=line_num,
                message=f"Phase '{phase}' declared in RUNSPEC but no [{missing}] found in PROPS",
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