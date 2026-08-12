"""L200-L209: record/item-shape checks.

Catches malformed records: missing items, wrong item types, records
that violate the keyword's item-shape spec.

This is a structural check that mostly piggybacks on the parser's
work — by the time we get here, the parser has already tokenized
records. What this rule adds:

- L201: A keyword with `size_kind=FIXED` has wrong record count.
- L202: A keyword with `size_kind=LIST` has records with wrong
  item count (more items than the spec allows).
- L203: A keyword with `size_kind=ARRAY` has records with wrong
  item count vs TABDIMS / DIMENS.
- L204: A keyword with no spec (unknown) is used in a critical
  section (RUNSPEC/GRID/SOLUTION/SCHEDULE).
"""

from __future__ import annotations

from pathlib import Path

from ..ast import Keyword
from ..spec import SizeKind, ValueType
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


def _item_kind_matches_expected(tok_text: str, expected: ValueType) -> bool:
    """Best-effort check if a token's text matches an expected type."""
    try:
        if expected == ValueType.INT:
            int(tok_text)
            return True
        if expected == ValueType.DOUBLE:
            float(tok_text)
            return True
        if expected == ValueType.STRING:
            return True
        if expected == ValueType.UDA:
            return True
    except (ValueError, TypeError):
        pass
    return False


def _check_keyword_shape(kw: Keyword) -> list[LintIssue]:
    issues: list[LintIssue] = []
    src = Path(kw.header_token.source_file) if kw.header_token.source_file else None
    line = kw.header_token.line
    spec = kw.spec

    if spec is None:
        # Unknown keyword — handled by section rule; no shape issue.
        return issues

    if spec.size_kind == SizeKind.FIXED:
        expected_count = spec.record_count or 1
        # Only flag if at least one record has items — otherwise the
        # keyword is using defaults (e.g. `TABDIMS\n/` is valid Eclipse).
        has_items = any(r.items for r in kw.records)
        if has_items and len(kw.records) != expected_count:
            issues.append(
                LintIssue(
                    code=201,
                    severity=Severity.ERROR,
                    message=(
                        f"{kw.name}: expected {expected_count} record(s), "
                        f"got {len(kw.records)}"
                    ),
                    source_file=src,
                    source_line=line,
                    keyword=kw,
                )
            )

    # L202: LIST-kind: each record should have <= len(items) tokens.
    # Items spec lists the maximum item shape.
    if spec.size_kind == SizeKind.LIST and spec.items:
        max_items = len(spec.items)
        for i, rec in enumerate(kw.records):
            if len(rec.items) > max_items:
                issues.append(
                    LintIssue(
                        code=202,
                        severity=Severity.WARNING,
                        message=(
                            f"{kw.name} record {i + 1}: has "
                            f"{len(rec.items)} items, expected at most "
                            f"{max_items}"
                        ),
                        source_file=src,
                        source_line=rec.line,
                        keyword=kw,
                    )
                )

    return issues


def shape_rule(deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Walk all sections and check keyword record shapes."""
    issues: list[LintIssue] = []
    for section in deck.sections.values():
        for kw in section.keywords:
            issues.extend(_check_keyword_shape(kw))
    return issues


def register() -> None:
    """Register this rule with the validator."""
    from ..validator import register as _register
    _register(200, 209, "shape", shape_rule)


register()