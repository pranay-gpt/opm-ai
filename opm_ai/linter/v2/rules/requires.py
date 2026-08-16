"""L240-L249: requires / prohibits.

Each KeywordSpec declares a list of `requires` (other keyword names
that must also appear) and `prohibits` (keyword names that must NOT
appear). At end of deck, check that:

- L241: every spec.requires is satisfied
- L242: every spec.prohibits pair is not violated (not implemented
  yet — reserved for a future phase).

Spec-level `requires` declarations are the single source of truth.
The catalogue defines them on each KeywordSpec (see catalogue/keywords.py
for the WELSPECS, COMPDAT, WCONPROD, WCONINJE, WCONHIST, WELOPEN,
WPIMULT, WTEMP, GCONPROD, GCONINJE pairs).
"""

from __future__ import annotations

from pathlib import Path

from ..ast import Deck
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


def _all_keyword_names(deck: Deck) -> set[str]:
    names: set[str] = set()
    for section in deck.sections.values():
        for kw in section.keywords:
            if kw.name:
                names.add(kw.name)
    return names


def requires_rule(deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Check that every keyword with spec.requires has its dependencies.

    Iterates every keyword in the deck whose spec declares `requires`,
    and emits L241 for any missing dependency. Spec-level declarations
    are the single source of truth (see catalogue/keywords.py).
    """
    issues: list[LintIssue] = []
    present = _all_keyword_names(deck)

    # Walk all keywords (deduplicated by name) and consult spec.requires.
    seen: set[str] = set()
    for section in deck.sections.values():
        for kw in section.keywords:
            if not kw.name or kw.name in seen:
                continue
            seen.add(kw.name)
            if kw.spec is None or not kw.spec.requires:
                continue
            for req in kw.spec.requires:
                if req not in present:
                    src = Path(kw.header_token.source_file) if kw.header_token.source_file else None
                    issues.append(
                        LintIssue(
                            code=241,
                            severity=Severity.ERROR,
                            message=(
                                f"{kw.name} requires {req}, "
                                f"but {req} is missing"
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
    _register(240, 249, "requires", requires_rule)


register()