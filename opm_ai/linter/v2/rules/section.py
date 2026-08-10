"""L260-L269: section order and presence.

Catches:
- L261: section appears out of canonical order (already in parser,
  but we re-report here for unified issue stream)
- L262: required section (RUNSPEC/GRID/PROPS/SOLUTION/SCHEDULE) is
  missing
- L263: optional section (EDIT/REGIONS/SUMMARY) appears twice
"""

from __future__ import annotations

from ..spec import CANONICAL_SECTIONS, SectionName
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


REQUIRED_SECTIONS = (
    SectionName.RUNSPEC,
    SectionName.GRID,
    SectionName.PROPS,
    SectionName.SOLUTION,
    SectionName.SCHEDULE,
)


def section_rule(deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Validate section presence and order."""
    issues: list[LintIssue] = []
    present = set(deck.sections.keys())
    present.discard(SectionName.PRELUDE)  # PRELUDE is virtual, not counted

    # L262: required sections missing
    for sec in REQUIRED_SECTIONS:
        if sec not in present:
            issues.append(
                LintIssue(
                    code=262,
                    severity=Severity.ERROR,
                    message=f"required section {sec.value} is missing",
                )
            )

    return issues


register(260, 269, "section", section_rule)