"""L270-L279: OPM Flow-specific rules.

OPM Flow has a specific subset of Eclipse keywords it supports.
This rule family flags keywords that Flow has in its catalogue
but does NOT actually consume at runtime (parsed but silently
ignored).

Phase 4 covers the most common offenders from the v1 documentation:
- CONFLICTING_KEYWORD (FULLIMP, GUIDE*, RUNSUM, SUMTHIN, SUREA, SURF*)
- "Unsupported in OPM Flow" cases

Note: POLYMER, FOAM, and the SURFACT/SURFACTW family are supported
by OPM Flow 2024+ and are deliberately NOT in this list.

Verified against opm-common master on 2026-08-12. Earlier lists
referenced "Pyrus documentation" (a third-party Eclipse IDE), but
Pyrus transcriptions drift and should not be the source of truth.
opm-common's handler files are.
"""

from __future__ import annotations

from pathlib import Path

from ..ast import Deck
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


# Keywords that OPM Flow has in its Eclipse catalogue but does NOT
# consume via a handler or state consumer. These keywords are
# parsed but silently dropped at simulation time.
#
# Excluded from this list (supported by OPM Flow 2024+):
#   - RUNSUM       — SummaryConfig.cpp (toggle RSM output)
#   - GUIDERAT     — GuideRateKeywordHandlers.cpp
#   - TRACER       — TracerConfig.cpp
#   - TRACERS      — Runspec.cpp::Tracers
#   - SUMTHIN      — KeywordHandlers.cpp (sumthin thinning)
#   - SUREA        — OPM-specific, supported (900_OPM)
#   - FULLIMP      — Catalog-only; harmless. OPM Flow's default solver mode.
#
# Excluded (not in opm-common catalogue at all — should be L016 unknown
# keyword if anything):
#   - NSUBS, SURFACE, PETRO
#
# POLYMER, FOAM, SURFACT/SURFACTW: supported by OPM Flow 2024+.
CATALOG_ONLY_OPM_KEYWORDS = frozenset({
    "PARTTRAC",
    "SURF",
})


def opm_rule(deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Flag keywords that OPM Flow has in its catalogue but does not
    consume. These are parsed but silently dropped at runtime."""
    issues: list[LintIssue] = []
    for section in deck.sections.values():
        for kw in section.keywords:
            if kw.name in CATALOG_ONLY_OPM_KEYWORDS:
                src = Path(kw.header_token.source_file) if kw.header_token.source_file else None
                issues.append(
                    LintIssue(
                        code=270,
                        severity=Severity.WARNING,
                        message=(
                            f"keyword {kw.name} is parsed by OPM Flow but "
                            f"has no handler (silently dropped at runtime)"
                        ),
                        source_file=src,
                        source_line=kw.header_token.line,
                        keyword=kw,
                    )
                )
    return issues


def register() -> None:
    """Register this rule with the validator."""
    from ..validator import register as _register
    _register(270, 279, "opm", opm_rule)


register()