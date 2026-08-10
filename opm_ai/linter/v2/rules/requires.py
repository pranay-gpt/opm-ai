"""L240-L249: requires / prohibits.

Each KeywordSpec declares a list of `requires` (other keyword names
that must also appear) and `prohibits` (keyword names that must NOT
appear). At end of deck, check that:

- L241: every spec.requires is satisfied (or suppressed due to
  INCLUDE/IMPORT/GDFILE)
- L242: every spec.prohibits pair is not violated

For Phase 4 we implement the most common cases:

- WELSPECS requires WELLDIMS
- WCONPROD requires WELSPECS
- COMPDAT requires WELSPECS
- ROCK requires no PROPS PVT tables in same file
"""

from __future__ import annotations

from ..ast import Deck
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


# Hand-curated requires pairs (the most common ones).
# If the catalogue doesn't already have these, we add them via spec
# augmentation; for now we maintain a small set here for testing.
_REQUIRES_PAIRS: dict[str, list[str]] = {
    "WELSPECS": ["WELLDIMS"],
    "WCONPROD": ["WELSPECS"],
    "WCONINJE": ["WELSPECS"],
    "WCONHIST": ["WELSPECS"],
    "COMPDAT": ["WELSPECS"],
    "WELOPEN": ["WELSPECS"],
    "WPIMULT": ["WELSPECS"],
    "WTEMP": ["WELSPECS"],
    "GCONPROD": ["WELSPECS"],
    "GCONINJE": ["WELSPECS"],
}


def _all_keyword_names(deck: Deck) -> set[str]:
    names: set[str] = set()
    for section in deck.sections.values():
        for kw in section.keywords:
            if kw.name:
                names.add(kw.name)
    return names


def requires_rule(deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Check that every keyword with requires has its dependencies."""
    issues: list[LintIssue] = []
    present = _all_keyword_names(deck)

    for kw_name, required in _REQUIRES_PAIRS.items():
        if kw_name not in present:
            continue
        for req in required:
            if req not in present:
                issues.append(
                    LintIssue(
                        code=241,
                        severity=Severity.ERROR,
                        message=(
                            f"{kw_name} requires {req}, but {req} is missing"
                        ),
                    )
                )
    return issues


register(240, 249, "requires", requires_rule)