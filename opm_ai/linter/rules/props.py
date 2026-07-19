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
    """Extract all values for a keyword as floats (handles multipliers like 500*100)."""
    values = []
    # Use \Z (end of string) instead of $ (end of line in MULTILINE mode)
    pattern = rf"(?is)^\s*{re.escape(keyword)}\b\s*(.*?)(?=^\s*[A-Z][A-Z0-9_]*\b|^\s*--|\Z)"
    match = re.search(pattern, section_text, re.MULTILINE | re.DOTALL)
    if match:
        content = match.group(1)
        tokens = content.split()
        for token in tokens:
            if token == "/":
                continue
            # Handle multiplier syntax: 500*100
            if "*" in token:
                parts = token.split("*")
                if len(parts) == 2:
                    try:
                        count = int(parts[0])
                        value = float(parts[1])
                        values.extend([value] * count)
                        continue
                    except ValueError:
                        pass
            try:
                values.append(float(token))
            except ValueError:
                pass
    return values


def rule_L005_pvt_phase_mismatch(deck: Deck) -> list[LintIssue]:
    """L005: Phase declared in RUNSPEC but missing companion PROPS keyword (ERROR).

    Requirements modelled on what Flow actually accepts:
    - WATER  -> PVTW
    - OIL    -> one of PVTO/PVDO/PVCDO/PVCO
    - GAS    -> one of PVTG/PVDG
    - DISGAS -> PVTO (live oil table)
    - VAPOIL -> PVTG (wet gas table)
    Saturation functions depend on the ACTIVE phase pairs, accepting both
    family I (SWOF/SGOF/SLGOF) and family II (SWFN/SGFN/SOF2/SOF3/SGWFN):
    - oil+water          -> SWOF, or SWFN with SOF2/SOF3
    - oil+gas            -> SGOF/SLGOF, or SGFN with SOF2/SOF3
    - gas+water (no oil) -> SGWFN, or SWFN with SGFN
    """
    issues = []

    runspec = deck.get_section("RUNSPEC")
    props = deck.get_section("PROPS")

    if not runspec or not props:
        return issues

    # PVT/saturation tables may live in included files, which the v1 linter
    # does not resolve - skip rather than false-positive (same policy as L003b)
    if _has_keyword(props, "INCLUDE"):
        return issues

    def _err(keyword: str, message: str) -> None:
        props_lines = deck.get_section_lines("PROPS")
        line_num = props_lines[0] if props_lines else None
        issues.append(LintIssue(
            severity="ERROR",
            section="PROPS",
            keyword=keyword,
            line=line_num,
            message=message,
            rule_id="L005"
        ))

    def _any(keywords: list[str]) -> bool:
        return any(_has_keyword(props, kw) for kw in keywords)

    oil = _has_keyword(runspec, "OIL")
    gas = _has_keyword(runspec, "GAS")
    water = _has_keyword(runspec, "WATER")
    disgas = _has_keyword(runspec, "DISGAS")
    vapoil = _has_keyword(runspec, "VAPOIL")

    # PVT tables per active phase (PVTWSALT is the brine variant of PVTW)
    if water and not _any(["PVTW", "PVTWSALT"]):
        _err("PVTW", "Phase 'WATER' declared in RUNSPEC but 'PVTW' (or PVTWSALT) not found in PROPS")
    if oil and not _any(["PVTO", "PVDO", "PVCDO", "PVCO"]):
        _err("PVTO", "Phase 'OIL' declared in RUNSPEC but no oil PVT table "
                     "(PVTO/PVDO/PVCDO/PVCO) found in PROPS")
    if gas and not _any(["PVTG", "PVDG"]):
        _err("PVTG/PVDG", "Phase 'GAS' declared in RUNSPEC but no gas PVT table "
                          "(PVTG/PVDG) found in PROPS")
    if disgas and not _has_keyword(props, "PVTO"):
        _err("PVTO", "'DISGAS' declared in RUNSPEC but live-oil table 'PVTO' not found in PROPS")
    if vapoil and not _has_keyword(props, "PVTG"):
        _err("PVTG", "'VAPOIL' declared in RUNSPEC but wet-gas table 'PVTG' not found in PROPS")

    # Saturation functions per active phase pair
    family2_oil = _any(["SOF2", "SOF3"])
    if oil and water:
        if not (_has_keyword(props, "SWOF") or (_has_keyword(props, "SWFN") and family2_oil)):
            _err("SWOF", "Phases 'OIL'+'WATER' active but no oil-water saturation "
                         "function (SWOF, or SWFN with SOF2/SOF3) found in PROPS")
    if oil and gas:
        if not (_any(["SGOF", "SLGOF"]) or (_has_keyword(props, "SGFN") and family2_oil)):
            _err("SGOF", "Phases 'OIL'+'GAS' active but no gas-oil saturation "
                         "function (SGOF/SLGOF, or SGFN with SOF2/SOF3) found in PROPS")
    if gas and water and not oil:
        if not (_has_keyword(props, "SGWFN")
                or (_has_keyword(props, "SWFN") and _has_keyword(props, "SGFN"))):
            _err("SGWFN", "Phases 'GAS'+'WATER' active but no gas-water saturation "
                          "function (SGWFN, or SWFN with SGFN) found in PROPS")

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

    # Get SATNUM values (floats from _get_keyword_values; regions are whole numbers)
    satnum_values = _get_keyword_values(regions, "SATNUM")
    max_satnum = max([int(v) for v in satnum_values if float(v).is_integer()], default=0)

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