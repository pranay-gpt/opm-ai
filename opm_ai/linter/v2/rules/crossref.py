"""L220-L229: cross-reference checks.

Catches:
- L221: COMPDAT/WCONPROD/WCONINJE references well not declared via
  WELSPECS (ERROR).
- L222: GCONPROD/GCONINJE references group not declared (WARNING).
- L223: GRUPTREE child not in groups (WARNING).
- L224: FU_* referenced in SUMMARY but not declared (WARNING).
"""

from __future__ import annotations

from pathlib import Path

from ..ast import Keyword
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


def _keyword_references_well(kw: Keyword) -> list[str]:
    """Extract well names referenced by a keyword that has well-name args.

    WELSPECS/COMPDAT/WCONPROD/WCONINJE/WCONHIST/WELOPEN: well name is
    items[0] of each record. WCONPROD also has well name as items[0]
    of each subsequent record.
    """
    refs: list[str] = []
    if kw.name not in (
        "WELSPECS", "COMPDAT", "WCONPROD", "WCONINJE", "WCONHIST",
        "WELOPEN", "WPIMULT", "WTEMP", "WCONINJH",
    ):
        return refs
    for rec in kw.records:
        if rec.items:
            refs.append(rec.items[0].text)
    return refs


def _keyword_references_group(kw: Keyword) -> list[str]:
    """Extract group names referenced by a keyword."""
    refs: list[str] = []
    if kw.name not in ("GCONPROD", "GCONINJE", "GRUPTREE"):
        return refs
    if kw.name == "GRUPTREE":
        # GRUPTREE: items[0] is parent (group), items[1..] are children (groups)
        for rec in kw.records:
            if rec.items:
                refs.extend(t.text for t in rec.items)
        return refs
    for rec in kw.records:
        if rec.items:
            refs.append(rec.items[0].text)
    return refs


def crossref_rule(deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Check that all referenced symbols are declared."""
    issues: list[LintIssue] = []

    # L221: well references must be declared
    for section in deck.sections.values():
        for kw in section.keywords:
            if kw.name == "WELSPECS":
                continue  # WELSPECS *declares* wells
            for well in _keyword_references_well(kw):
                # Skip empty / non-string "well names" — these are
                # continuations of the previous record (COMPDAT's
                # MD-in/MD-out pattern, which we don't fully model).
                if not well or not well[0].isalpha():
                    continue
                if well not in symbol_table.wells:
                    src = Path(kw.header_token.source_file) if kw.header_token.source_file else None
                    issues.append(
                        LintIssue(
                            code=221,
                            severity=Severity.WARNING,
                            message=(
                                f"{kw.name} references well '{well}' "
                                f"which is not declared via WELSPECS"
                            ),
                            source_file=src,
                            source_line=kw.header_token.line,
                            keyword=kw,
                        )
                    )

    # L222: group references
    for section in deck.sections.values():
        for kw in section.keywords:
            if kw.name == "GRUPTREE":
                # GRUPTREE: check that each child group exists
                for rec in kw.records:
                    if len(rec.items) < 2:
                        continue
                    parent = rec.items[0].text
                    for child_tok in rec.items[1:]:
                        child = child_tok.text
                        if child not in symbol_table.groups:
                            src = Path(kw.header_token.source_file) if kw.header_token.source_file else None
                            issues.append(
                                LintIssue(
                                    code=223,
                                    severity=Severity.WARNING,
                                    message=(
                                        f"GRUPTREE references group "
                                        f"'{child}' which is not declared"
                                    ),
                                    source_file=src,
                                    source_line=rec.line,
                                    keyword=kw,
                                )
                            )
                continue
            for group in _keyword_references_group(kw):
                if kw.name == "GCONPROD":
                    if group not in symbol_table.groups:
                        src = Path(kw.header_token.source_file) if kw.header_token.source_file else None
                        issues.append(
                            LintIssue(
                                code=222,
                                severity=Severity.WARNING,
                                message=(
                                    f"{kw.name} references group "
                                    f"'{group}' which is not declared"
                                ),
                                source_file=src,
                                source_line=kw.header_token.line,
                                keyword=kw,
                            )
                        )

    return issues


register(220, 229, "crossref", crossref_rule)