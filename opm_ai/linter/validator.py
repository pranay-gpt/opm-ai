"""Layer 2 validator - schema-driven lint checks.

Phase 3 of the linter-redesign plan. This module consumes the YAML
specs loaded by `opm_ai.linter.spec.load_spec` and emits LintIssues
for every spec-derived violation it finds in a Deck.

Layer separation rationale (see docs/personal/LINTER_REDESIGN_PLAN.md):
- L1 / L3 layer (opm_ai.linter.rules.*): cross-keyword reasoning,
  recognition, syntactic checks. 18 rules.
- L2 layer (this module): per-keyword presence / count / range
  checks driven by hand-curated YAML specs.

L2 issue rule_ids follow the namespace `L2.<KEYWORD>.<CHECK>` so
downstream consumers can filter: an API response can ask for "all
L2 issues" or "just L2.WELLDIMS.required".

Phase 3 ships three checks: required, item_count, item_range. The
rest (mutually_exclusive, multi-record keywords, repeated: true
items) arrive in Phase 3.5.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue
from opm_ai.linter.spec import KeywordSpec

log = logging.getLogger(__name__)


# Match the keyword at the start of a line (case-insensitive). Same
# semantics as `_has_keyword` in rules/runspec.py:12.
_KEYWORD_LINE_RE = re.compile(rf"(?im)^\s*{re.escape('{NAME}')}\b")


def _has_keyword(section_text: str, keyword: str) -> bool:
    """True iff `keyword` appears as the first token on a non-comment line."""
    pattern = rf"(?im)^\s*{re.escape(keyword)}\b"
    return bool(re.search(pattern, section_text))


def _section_includes(section_text: str) -> bool:
    """True if the section contains an INCLUDE keyword.

    When a section pulls its content from an INCLUDE'd file, the linter
    cannot resolve which keywords are present. Both L1/L3 rules and L2
    skip the section in that case to avoid false positives (e.g. SPE5
    imports DIMENS from SPE5.BASE).
    """
    return _has_keyword(section_text, "INCLUDE")


def validate(deck: Deck, specs: dict[str, KeywordSpec]) -> list[LintIssue]:
    """Run every L2 check against the deck using the given specs.

    Each spec contributes zero or more LintIssues. Issues are sorted
    by (section, keyword, line) for stable output across runs.

    Args:
        deck: parsed deck.
        specs: dict from `load_spec(spec_dir)`.

    Returns:
        list of LintIssue. Empty list if every spec passes.
    """
    issues: list[LintIssue] = []
    for spec in specs.values():
        issues.extend(_check_required(deck, spec))
        issues.extend(_check_item_count(deck, spec))
        issues.extend(_check_item_ranges(deck, spec))
    return issues


# ---------------------------------------------------------------------- #
# Check: required                                                        #
# ---------------------------------------------------------------------- #

def _check_required(deck: Deck, spec: KeywordSpec) -> list[LintIssue]:
    """ERROR if `required: true` and keyword absent from its section.

    Skipped when the section contains INCLUDE (the keyword may live in
    an included file, which the v1 linter does not resolve).
    """
    if not spec.required:
        return []
    section_text = deck.get_section(spec.section) or ""
    if _section_includes(section_text):
        return []
    if _has_keyword(section_text, spec.name):
        return []
    section_lines = deck.get_section_lines(spec.section)
    line_num = section_lines[0] if section_lines else None
    return [LintIssue(
        severity="ERROR",
        section=spec.section,
        keyword=spec.name,
        line=line_num,
        message=(
            f"{spec.section} must contain {spec.name} keyword "
            f"(spec declares it required)"
        ),
        rule_id=f"L2.{spec.name}.required",
    )]


# ---------------------------------------------------------------------- #
# Check: item_count                                                      #
# ---------------------------------------------------------------------- #

def _find_first_record_lines(deck: Deck, spec: KeywordSpec) -> list[tuple[int, str]]:
    """Return [(deck_line, line_text)] of data lines for the keyword's first record.

    Recognises two record layouts:
    1. Header on its own line, data on subsequent lines (until a new
       keyword or terminator): `WELLDIMS\n  5 2 1 9 /`
    2. Header and data on the same line: `TABDIMS 1 1 1 1 1 1 /`
    3. Header alone with no data — return [] (degenerate case, treated
       as "use all defaults"; count and range checks skipped).

    Multi-record keywords (repeated: true) are out of scope for Phase 3.
    """
    section_text = deck.get_section(spec.section)
    if not section_text:
        return []
    section_lines = deck.get_section_lines(spec.section)
    if not section_lines:
        return []
    start, end = section_lines
    out: list[tuple[int, str]] = []
    found_header = False
    for deck_line, line in enumerate(section_text.split("\n"), start):
        if deck_line > end:
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        # Match the keyword header (case-insensitive).
        m = re.match(rf"(?i)^\s*{re.escape(spec.name)}\b(.*)$", stripped)
        if m and not found_header:
            found_header = True
            tail = m.group(1).strip()
            # If the header line has no tail data, the keyword record
            # is degenerate (no items; rely on defaults).
            if not tail or tail == "/":
                return []  # degenerate: skip count/range checks.
            # If the header line has trailing data, that's the record.
            if tail:
                out.append((deck_line, stripped))
                return out
            # Header line is empty; data follows on next lines.
            continue
        if not found_header:
            continue
        # Subsequent lines: data lines until terminator or new keyword.
        if stripped == "/" or stripped.startswith("/"):
            return out
        if re.match(r"^[A-Z][A-Z0-9_]*\b", stripped):
            # New keyword header reached; the current record is done.
            return out
        out.append((deck_line, stripped))
    return out


def _tokenize_record(line: str) -> list[str]:
    """Split an Eclipse record line on whitespace, treating `1*` as a skip marker.

    Quotes are stripped from quoted tokens. `--` cuts a trailing comment.
    Eclipse record format allows `1*` (use default) and `n*` (repeat
    default n times). For Phase 3 we treat `1*` as a single skip token;
    `n*` for n > 1 would expand to n items in a complete implementation
    but Phase 3 only sees WELLDIMS where `n*` is unusual.

    Returns an empty list if the line is empty / comment-only after
    stripping.
    """
    # Strip inline comments first.
    no_comment = line.split("--", 1)[0].strip()
    # Strip record terminator.
    if "/" in no_comment:
        no_comment = no_comment.split("/", 1)[0].strip()
    if not no_comment:
        return []
    # Tokenise on whitespace; strip quotes from each token.
    tokens: list[str] = []
    for tok in no_comment.split():
        # 1* = use default; phase 3 just counts it as one item.
        if tok == "1*":
            tokens.append(tok)
            continue
        if tok.endswith("*") and tok[:-1].isdigit():
            tokens.append(tok)
            continue
        # Quoted string: strip quotes.
        if (tok.startswith("'") and tok.endswith("'") and len(tok) >= 2):
            tokens.append(tok[1:-1])
            continue
        if (tok.startswith('"') and tok.endswith('"') and len(tok) >= 2):
            tokens.append(tok[1:-1])
            continue
        tokens.append(tok)
    return tokens


def _check_item_count(deck: Deck, spec: KeywordSpec) -> list[LintIssue]:
    """ERROR if the keyword's first record has fewer or more items than spec.

    Multi-record keywords (repeated: true) are out of scope; we only
    check the first record. Phase 3.5 will introduce per-record checks.

    Item-count bounds come from `spec.effective_min_items` and
    `spec.effective_max_items` (default: 1 and len(items)). For
    keywords like WELLDIMS where items 5-12 default to 0, set
    `min_items: 1` in the YAML so a 4-item record is accepted.
    """
    if not spec.items:
        return []
    expected_min = spec.effective_min_items
    expected_max = spec.effective_max_items
    record_lines = _find_first_record_lines(deck, spec)
    if not record_lines:
        # Keyword absent or has no data; _check_required catches that.
        return []
    first_line_num, first_line_text = record_lines[0]
    try:
        tokens = _tokenize_record(first_line_text)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("could not tokenize %s record: %s", spec.name, exc)
        return [_record_unparseable(spec, first_line_num, exc)]
    actual = len(tokens)
    if expected_min <= actual <= expected_max:
        return []
    if actual > expected_max:
        hint = "more items than declared in spec"
    else:
        hint = "fewer items than declared in spec"
    return [LintIssue(
        severity="ERROR",
        section=spec.section,
        keyword=spec.name,
        line=first_line_num,
        message=(
            f"{spec.name} record has {actual} items, spec accepts "
            f"{expected_min}-{expected_max} ({hint})"
        ),
        rule_id=f"L2.{spec.name}.item_count",
    )]


# ---------------------------------------------------------------------- #
# Check: item_range                                                      #
# ---------------------------------------------------------------------- #

def _check_item_ranges(deck: Deck, spec: KeywordSpec) -> list[LintIssue]:
    """ERROR if any item value is outside the spec's range.

    Skips non-numeric items (string, keyword, flag) and items with
    no range constraint. Honours `strict_min` / `strict_max` from
    SpecItem (default: inclusive bounds).
    """
    if not spec.items:
        return []
    record_lines = _find_first_record_lines(deck, spec)
    if not record_lines:
        return []
    first_line_num, first_line_text = record_lines[0]
    try:
        tokens = _tokenize_record(first_line_text)
    except Exception as exc:  # pragma: no cover - defensive
        return [_record_unparseable(spec, first_line_num, exc)]

    issues: list[LintIssue] = []
    for idx, item in enumerate(spec.items):
        if item.range is None:
            continue
        if item.type not in ("int", "float"):
            continue
        if idx >= len(tokens):
            break  # _check_item_count will fire on the count mismatch.
        raw = tokens[idx]
        # `1*` means "use default"; cannot range-check.
        if raw.endswith("*"):
            continue
        try:
            value = float(raw) if item.type == "float" else int(raw)
        except ValueError:
            # Token isn't a number; flag as range violation with the raw text.
            issues.append(LintIssue(
                severity="ERROR",
                section=spec.section,
                keyword=spec.name,
                line=first_line_num,
                message=(
                    f"{spec.name} item {idx + 1} ({item.name}) is {raw!r}; "
                    f"expected a number in range {item.range}"
                ),
                rule_id=f"L2.{spec.name}.range",
            ))
            continue
        lo, hi = item.range
        # Optional int-as-float coercion for ranges whose bounds happen
        # to be whole numbers but the type says int.
        if item.type == "int":
            lo_n: float | int = int(lo)
            hi_n: float | int = int(hi)
        else:
            lo_n, hi_n = lo, hi
        out_of_range = (
            (value < lo_n and item.strict_min) or (value <= lo_n - 1 and not item.strict_min)
            or (value > hi_n and item.strict_max) or (value >= hi_n + 1 and not item.strict_max)
        )
        # Cleaner logic: re-derive
        if item.strict_min:
            too_low = value <= lo_n
        else:
            too_low = value < lo_n
        if item.strict_max:
            too_high = value >= hi_n
        else:
            too_high = value > hi_n
        if too_low or too_high:
            where = "below" if too_low else "above"
            issues.append(LintIssue(
                severity="ERROR",
                section=spec.section,
                keyword=spec.name,
                line=first_line_num,
                message=(
                    f"{spec.name} item {idx + 1} ({item.name}) is {value} "
                    f"({where} spec range {item.range})"
                ),
                rule_id=f"L2.{spec.name}.range",
            ))
    return issues


def _record_unparseable(spec: KeywordSpec, line: int, exc: Exception) -> LintIssue:
    """Helper: a single WARNING for an unparseable record.

    Skipping is preferable to ERRORing because we can't tell whether
    the value is out of range or merely formatted oddly. The user
    sees a hint; the build doesn't fail.
    """
    return LintIssue(
        severity="WARNING",
        section=spec.section,
        keyword=spec.name,
        line=line,
        message=(
            f"could not parse {spec.name} record on line {line} "
            f"({type(exc).__name__}: {exc}); skipping item checks"
        ),
        rule_id=f"L2.{spec.name}.parse",
    )


__all__ = ["validate"]
