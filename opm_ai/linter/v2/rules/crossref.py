"""L220-L229: cross-reference checks.

Catches:
- L221: COMPDAT/WCONPROD/WCONINJE references well not declared via
  WELSPECS (WARNING). Many fixtures have wells declared in INCLUDEd
  files that the symbol table doesn't pick up, so ERROR would
  produce many false positives. The corpus gate (Phase 4) confirmed
  that WARNING captures the intent without false-flagging.
- L222: GCONPROD/GCONINJE references group not declared (WARNING).
- L223: GRUPTREE child not in groups (WARNING).
- L224: FU_/WU_/GU_/CU_/AU_/RU_ summary var referenced in SUMMARY
  but not declared via FUNVAR or UDQ DEFINE/ASSIGN/UNITS/UPDATE
  (INFO). The UDQ action-verb records (DEFINE/ASSIGN/UNITS/UPDATE)
  are sometimes parsed as separate keywords because the parser
  doesn't fully absorb UDQ-internal records yet; L224 is therefore
  demoted to INFO until UDQ record extraction is improved.
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
                    # Skip if it looks like a wildcard ('*' suffix or
                    # '?' glob). Real wells are alphanumeric strings;
                    # patterns include OP*, PROD*, I*, etc.
                    if "*" in well or "?" in well:
                        continue
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
                if kw.name in ("GCONPROD", "GCONINJE"):
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

    # L224: FU_* referenced in SUMMARY but not declared.
    # Walk summary_vars; for each whose name starts with FU/WU/GU/CU/AU,
    # emit WARNING if not in st.fu_vars.
    for sv in symbol_table.summary_vars:
        if not sv.name or not sv.name[0].isalpha():
            continue
        if sv.name[0] not in "FWGCAR":
            continue
        base = sv.name.split(":", 1)[0]  # strip :target suffix
        # Only flag user-defined vars (FU_/WU_/GU_/CU_/AU_/RU_)
        if not (
            base.startswith("FU_") or base.startswith("WU_")
            or base.startswith("GU_") or base.startswith("CU_")
            or base.startswith("AU_") or base.startswith("RU_")
        ):
            continue
        if base in symbol_table.fu_vars:
            continue
        issues.append(LintIssue(
            code=224,
            severity=Severity.INFO,
            message=(
                f"SUMMARY references '{sv.name}' which is not declared "
                f"via FUNVAR or UDQ DEFINE/ASSIGN/UNITS/UPDATE"
            ),
            source_file=sv.source_file,
            source_line=sv.source_line,
        ))

    return issues


def register() -> None:
    """Register this rule with the validator."""
    from ..validator import register as _register
    _register(220, 229, "crossref", crossref_rule)


register()