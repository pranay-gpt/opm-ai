"""L260-L269: section order and presence.

Catches:
- L261: section appears out of canonical order (not implemented —
  the parser at parser.py:L141 records this already; re-reporting
  from the rule layer is reserved for a future phase).
- L262: required section (RUNSPEC/GRID/PROPS/SOLUTION/SCHEDULE) is
  missing (ERROR).
- L263: optional section (EDIT/REGIONS/SUMMARY) appears twice
  (not implemented — reserved for a future phase).

Note: L170 (keyword used in a section not in its catalogue section
list) and L171 (unknown keyword) live in `rules/section_validity.py`.
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


def register() -> None:
    """Register this rule with the validator."""
    from ..validator import register as _register
    _register(260, 269, "section", section_rule)


register()