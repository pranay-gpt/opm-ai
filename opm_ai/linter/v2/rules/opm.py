"""L270-L279: OPM Flow-specific rules.

OPM Flow has a specific subset of Eclipse keywords it supports.
This rule family flags keywords that Flow rejects.

Phase 4 covers the most common offenders from the v1 documentation:
- CONFLICTING_KEYWORD (FULLIMP, GUIDE*, RUNSUM, SUMTHIN, SUREA, SURF*)
- "Unsupported in OPM Flow" cases

We surface these as ERROR / WARNING to match the v1 behaviour.
"""

from __future__ import annotations

from pathlib import Path

from ..ast import Deck
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


# Keywords that OPM Flow does not support (per Pyrus documentation).
UNSUPPORTED_OPM_KEYWORDS = frozenset({
    "FULLIMP",
    "GUIDE_RATE",
    "GUIDERAT",
    "RUNSUM",
    "SUMTHIN",
    "SUREA",
    "SURF",
    "SURFACT",
    "SURFACTW",
    "NSUBS",
    "PETRO",
    "PARTTRAC",
    "TRACER",
    "TRACERS",  # sometimes supported — TODO check
    "POLYMER",
    "FOAM",
    "SURFACE",
})


def opm_rule(deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Flag keywords that OPM Flow does not support."""
    issues: list[LintIssue] = []
    for section in deck.sections.values():
        for kw in section.keywords:
            if kw.name in UNSUPPORTED_OPM_KEYWORDS:
                src = Path(kw.header_token.source_file) if kw.header_token.source_file else None
                issues.append(
                    LintIssue(
                        code=270,
                        severity=Severity.WARNING,
                        message=(
                            f"keyword {kw.name} is not supported by "
                            f"OPM Flow (per Pyrus docs)"
                        ),
                        source_file=src,
                        source_line=kw.header_token.line,
                        keyword=kw,
                    )
                )
    return issues


register(270, 279, "opm", opm_rule)