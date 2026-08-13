"""L230-L239: dimension consistency.

Catches:
- L231: TABDIMS NSSFUN=N vs count of distinct SWOF/SGOF records.
- L232: WELLDIMS MAXWELLS=N vs count of WELSPECS records (must not exceed).
- L233: EQLDIMS NTEQUL=N vs count of EQUIL records.
- L234: REGDIMS NTFIP=N vs count of distinct FIPNUM regions.
- L235: ACTDIMS NMAXACTIONS=N vs count of ACTIONX blocks.

Phase 4 implements L232 (WELLDIMS vs WELSPECS) and L234 (REGDIMS vs FIPNUM)
which are the most commonly violated.
"""

from __future__ import annotations

from pathlib import Path

from ..ast import Keyword
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


def _tokens_ints(items) -> list[int]:
    out: list[int] = []
    for t in items:
        try:
            out.append(int(t.text))
        except (ValueError, TypeError):
            pass
    return out


def dims_rule(deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Check dimension consistency between limit keywords and contents."""
    issues: list[LintIssue] = []

    # L232: WELLDIMS MAXWELLS vs WELSPECS count
    welldims = _find_keyword(deck, "WELLDIMS")
    if welldims and welldims.records and welldims.records[0].items:
        ints = _tokens_ints(welldims.records[0].items)
        if ints:
            max_wells = ints[0]
            actual_wells = symbol_table.well_count()
            if actual_wells > max_wells:
                src = Path(welldims.header_token.source_file) if welldims.header_token.source_file else None
                issues.append(
                    LintIssue(
                        code=232,
                        severity=Severity.ERROR,
                        message=(
                            f"WELLDIMS MAXWELLS={max_wells} but "
                            f"{actual_wells} wells declared via WELSPECS"
                        ),
                        source_file=src,
                        source_line=welldims.header_token.line,
                        keyword=welldims,
                    )
                )

    # L234: REGDIMS NTFIP vs distinct FIPNUM regions.
    # Eclipse convention: NTFIP is a capacity, not a strict max.
    # OPM Flow accepts decks with regions > NTFIP (it allocates
    # more dynamically), so flag this as WARNING rather than ERROR.
    # Use fipnum_regions specifically — SATNUM/PVTNUM/EQLNUM have
    # their own dimension keys (TABDIMS NSSFUN, REGDIMS NTPVT,
    # EQLDIMS NTEQUL) and must not contaminate the FIPNUM check.
    regdims = _find_keyword(deck, "REGDIMS")
    if regdims and regdims.records and regdims.records[0].items:
        ints = _tokens_ints(regdims.records[0].items)
        if ints:
            ntfip = ints[0]
            max_region = max(symbol_table.fipnum_regions) if symbol_table.fipnum_regions else 0
            if max_region > ntfip:
                src = Path(regdims.header_token.source_file) if regdims.header_token.source_file else None
                issues.append(
                    LintIssue(
                        code=234,
                        severity=Severity.WARNING,
                        message=(
                            f"REGDIMS NTFIP={ntfip} but max FIPNUM region "
                            f"is {max_region} (Flow may allocate more)"
                        ),
                        source_file=src,
                        source_line=regdims.header_token.line,
                        keyword=regdims,
                    )
                )

    # L233: EQLDIMS NTEQUL vs EQUIL count.
    # NTEQUL is a capacity. Flow tolerates more EQUIL records than
    # the declared capacity (just as it does for FIPNUM).
    eqldims = _find_keyword(deck, "EQLDIMS")
    if eqldims and eqldims.records and eqldims.records[0].items:
        ints = _tokens_ints(eqldims.records[0].items)
        if ints:
            ntequl = ints[0]
            equil_kw = _find_keyword(deck, "EQUIL")
            equil_count = len(equil_kw.records) if equil_kw else 0
            if equil_count > ntequl + 1:
                src = Path(eqldims.header_token.source_file) if eqldims.header_token.source_file else None
                issues.append(
                    LintIssue(
                        code=233,
                        severity=Severity.WARNING,
                        message=(
                            f"EQLDIMS NTEQUL={ntequl} allows up to "
                            f"{ntequl + 1} EQUIL records but "
                            f"{equil_count} found"
                        ),
                        source_file=src,
                        source_line=eqldims.header_token.line,
                        keyword=eqldims,
                    )
                )

    return issues


def _find_keyword(deck, name: str) -> Keyword | None:
    for section in deck.sections.values():
        for kw in section.keywords:
            if kw.name == name:
                return kw
    return None


def register() -> None:
    """Register this rule with the validator."""
    from ..validator import register as _register
    _register(230, 239, "dims", dims_rule)


register()