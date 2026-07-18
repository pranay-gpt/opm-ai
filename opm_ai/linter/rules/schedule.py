"""SCHEDULE section lint rules - L006, L007, L008, L014, L015."""

import re
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue


def _has_keyword(section_text: str, keyword: str) -> bool:
    """Check if keyword exists in section."""
    pattern = rf"(?im)^\s*{re.escape(keyword)}\b"
    return bool(re.search(pattern, section_text))


def _get_keyword_values(section_text: str, keyword: str) -> list[str]:
    """Extract all values for a keyword."""
    values = []
    pattern = rf"(?is)^\s*{re.escape(keyword)}\b\s*(.*?)(?=^\s*[A-Z][A-Z0-9_]*\b|^\s*--|$)"
    match = re.search(pattern, section_text, re.MULTILINE | re.DOTALL)
    if match:
        content = match.group(1)
        tokens = content.split()
        for token in tokens:
            if token != "/":
                values.append(token)
    return values


def _extract_well_names(section_text: str, keyword: str) -> list[str]:
    """Extract well names from WELSPECS keyword."""
    wells = []
    pattern = rf"(?is)^\s*{re.escape(keyword)}\b\s*(.*?)(?=^\s*[A-Z][A-Z0-9_]*\b|^\s*--|$)"
    match = re.search(pattern, section_text, re.MULTILINE | re.DOTALL)
    if match:
        content = match.group(1)
        # Well names are typically in single quotes
        well_names = re.findall(r"'([^']+)'", content)
        wells.extend(well_names)
    return wells


def _is_producer(section_text: str, well_name: str) -> bool:
    """Check if well is a producer (has OIL in WELSPECS)."""
    # WELSPECS format: WELLNAME I J BHP PHASE ...
    # Phase is typically 5th item after name
    pattern = rf"'{re.escape(well_name)}'.*?'OIL'"
    return bool(re.search(pattern, section_text, re.IGNORECASE))


def _is_injector(section_text: str, well_name: str) -> bool:
    """Check if well is an injector (has GAS or WATER in WELSPECS)."""
    pattern = rf"'{re.escape(well_name)}'.*?(?:GAS|WATER)"
    return bool(re.search(pattern, section_text, re.IGNORECASE))


def rule_L006_wellspecs_no_compdat(deck: Deck) -> list[LintIssue]:
    """L006: WELSPECS present but COMPDAT missing (ERROR)."""
    issues = []

    schedule = deck.get_section("SCHEDULE")
    if not schedule:
        return issues

    if _has_keyword(schedule, "WELSPECS") and not _has_keyword(schedule, "COMPDAT"):
        sched_lines = deck.get_section_lines("SCHEDULE")
        line_num = sched_lines[0] if sched_lines else None
        issues.append(LintIssue(
            severity="ERROR",
            section="SCHEDULE",
            keyword="COMPDAT",
            line=line_num,
            message="WELSPECS present but COMPDAT missing - wells have no completions",
            rule_id="L006"
        ))

    return issues


def rule_L007_well_not_in_wellspecs(deck: Deck) -> list[LintIssue]:
    """L007: Well in COMPDAT/WCONPROD/WCONINJE not declared in WELSPECS (ERROR)."""
    issues = []

    schedule = deck.get_section("SCHEDULE")
    if not schedule:
        return issues

    if not _has_keyword(schedule, "WELSPECS"):
        return issues

    wells = _extract_well_names(schedule, "WELSPECS")
    well_set = set(wells)

    # Check COMPDAT wells
    if _has_keyword(schedule, "COMPDAT"):
        compdat_wells = _extract_well_names(schedule, "COMPDAT")
        for well in compdat_wells:
            if well not in well_set:
                sched_lines = deck.get_section_lines("SCHEDULE")
                line_num = sched_lines[0] if sched_lines else None
                issues.append(LintIssue(
                    severity="ERROR",
                    section="SCHEDULE",
                    keyword="COMPDAT",
                    line=line_num,
                    message=f"Well '{well}' in COMPDAT but not declared in WELSPECS",
                    rule_id="L007"
                ))

    # Check WCONPROD wells
    if _has_keyword(schedule, "WCONPROD"):
        wconprod_wells = _extract_well_names(schedule, "WCONPROD")
        for well in wconprod_wells:
            if well not in well_set:
                sched_lines = deck.get_section_lines("SCHEDULE")
                line_num = sched_lines[0] if sched_lines else None
                issues.append(LintIssue(
                    severity="ERROR",
                    section="SCHEDULE",
                    keyword="WCONPROD",
                    line=line_num,
                    message=f"Well '{well}' in WCONPROD but not declared in WELSPECS",
                    rule_id="L007"
                ))

    # Check WCONINJE wells
    if _has_keyword(schedule, "WCONINJE"):
        wconinje_wells = _extract_well_names(schedule, "WCONINJE")
        for well in wconinje_wells:
            if well not in well_set:
                sched_lines = deck.get_section_lines("SCHEDULE")
                line_num = sched_lines[0] if sched_lines else None
                issues.append(LintIssue(
                    severity="ERROR",
                    section="SCHEDULE",
                    keyword="WCONINJE",
                    line=line_num,
                    message=f"Well '{well}' in WCONINJE but not declared in WELSPECS",
                    rule_id="L007"
                ))

    return issues


def rule_L008_wellspecs_auto_no_gruptree(deck: Deck) -> list[LintIssue]:
    """L008: WELSPECS group = AUTO but no GRUPTREE in deck (ERROR)."""
    issues = []

    schedule = deck.get_section("SCHEDULE")
    if not schedule:
        return issues

    if not _has_keyword(schedule, "WELSPECS"):
        return issues

    # Check if any well has group AUTO
    lines = schedule.split("\n")
    in_wellspecs = False
    for line in lines:
        stripped = line.strip().upper()
        if stripped.startswith("WELSPECS"):
            in_wellspecs = True
            continue
        if in_wellspecs and stripped.startswith("/"):
            in_wellspecs = False
            continue
        if in_wellspecs and "AUTO" in stripped:
            # Found AUTO group
            if not _has_keyword(schedule, "GRUPTREE") and not _has_keyword(schedule, "GROUP"):
                # Also check entire deck for GRUPTREE
                has_gruptree = False
                for section_name in deck.sections:
                    sec_text = deck.get_section(section_name)
                    if sec_text and _has_keyword(sec_text, "GRUPTREE"):
                        has_gruptree = True
                        break

                if not has_gruptree:
                    sched_lines = deck.get_section_lines("SCHEDULE")
                    line_num = sched_lines[0] if sched_lines else None
                    issues.append(LintIssue(
                        severity="ERROR",
                        section="SCHEDULE",
                        keyword="GRUPTREE",
                        line=line_num,
                        message="WELSPECS group AUTO requires GRUPTREE definition",
                        rule_id="L008"
                    ))
            break

    return issues


def rule_L014_producer_no_wconprod(deck: Deck) -> list[LintIssue]:
    """L014: Producer well without WCONPROD (ERROR)."""
    issues = []

    schedule = deck.get_section("SCHEDULE")
    if not schedule:
        return issues

    if not _has_keyword(schedule, "WELSPECS"):
        return issues

    wells = _extract_well_names(schedule, "WELSPECS")
    producer_wells = [w for w in wells if _is_producer(schedule, w)]

    if producer_wells and not _has_keyword(schedule, "WCONPROD"):
        sched_lines = deck.get_section_lines("SCHEDULE")
        line_num = sched_lines[0] if sched_lines else None
        issues.append(LintIssue(
            severity="ERROR",
            section="SCHEDULE",
            keyword="WCONPROD",
            line=line_num,
            message=f"Producer well(s) {', '.join(producer_wells)} defined but WCONPROD missing",
            rule_id="L014"
        ))

    return issues


def rule_L015_injector_no_wconinje(deck: Deck) -> list[LintIssue]:
    """L015: Injector well without WCONINJE (ERROR)."""
    issues = []

    schedule = deck.get_section("SCHEDULE")
    if not schedule:
        return issues

    if not _has_keyword(schedule, "WELSPECS"):
        return issues

    wells = _extract_well_names(schedule, "WELSPECS")
    injector_wells = [w for w in wells if _is_injector(schedule, w)]

    if injector_wells and not _has_keyword(schedule, "WCONINJE"):
        sched_lines = deck.get_section_lines("SCHEDULE")
        line_num = sched_lines[0] if sched_lines else None
        issues.append(LintIssue(
            severity="ERROR",
            section="SCHEDULE",
            keyword="WCONINJE",
            line=line_num,
            message=f"Injector well(s) {', '.join(injector_wells)} defined but WCONINJE missing",
            rule_id="L015"
        ))

    return issues