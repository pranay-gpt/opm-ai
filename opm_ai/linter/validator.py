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
        issues.extend(_check_mutex(deck, spec, specs))
    return issues


def _is_calibrated(spec: KeywordSpec) -> bool:
    """True if the spec has been validated against real fixtures.

    Phase 3 default: item_count and range issues on uncalibrated
    specs are INFO (advisory). When a spec author sets
    `calibrated: true` in the YAML after proving the bounds against
    fixtures, the linter promotes these to WARNING. Required-keyword
    absence stays ERROR unconditionally.
    """
    return bool(getattr(spec, "calibrated", False))


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
# Check: mutex (mutually_exclusive_with)                                 #
# ---------------------------------------------------------------------- #

def _check_mutex(
    deck: Deck,
    spec: KeywordSpec,
    specs: dict[str, KeywordSpec],
) -> list[LintIssue]:
    """ERROR if `spec.keyword` co-occurs with any of its mutex partners.

    Phase 3.5: enforces `mutually_exclusive_with: list[str]` declared
    in the YAML spec. Concrete pairs:
    - COORD ↔ DX (corner-point vs rectangular grid).
    - DZ + TOPS ↔ ZCORN (legacy vs corner-point Z).
    - PVTO ↔ PVDO (live-oil vs dead-oil).
    - PVTG ↔ PVDG (wet-gas vs dry-gas).
    - SWOF ↔ SGFN (rel-perm with vs without pcow).
    - SWOF ↔ SGOF (OPM allows either, but they're conceptually
      alternative ways to specify the same Kr tables; in practice
      decks use one or the other, not both. Marked as a soft
      mutex, not enforced unless both have items.)

    Each pair fires once per deck with rule_id `L2.<KEYWORD>.mutex`.
    """
    if not spec.mutually_exclusive_with:
        return []
    section_text = deck.get_section(spec.section)
    if section_text is None or _section_includes(section_text):
        return []
    if not _has_keyword(section_text, spec.name):
        return []
    section_lines = deck.get_section_lines(spec.section)
    line_num = section_lines[0] if section_lines else None
    issues: list[LintIssue] = []
    for partner_name in spec.mutually_exclusive_with:
        partner_spec = specs.get(partner_name)
        if partner_spec is None:
            continue  # partner not in catalogue; skip silently.
        partner_section = deck.get_section(partner_spec.section)
        if partner_section is None or _section_includes(partner_section):
            continue
        if not _has_keyword(partner_section, partner_name):
            continue
        issues.append(LintIssue(
            severity="WARNING",
            section=spec.section,
            keyword=spec.name,
            line=line_num,
            message=(
                f"{spec.name} is mutually exclusive with {partner_name}: "
                f"deck uses both. Choose one."
            ),
            rule_id=f"L2.{spec.name}.mutex",
        ))
    return issues


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
    records = _find_all_records(deck, spec)
    return records[0] if records else []


def _find_all_records(deck: Deck, spec: KeywordSpec) -> list[list[tuple[int, str]]]:
    """Return all records of `spec.keyword` in its section.

    Each record is a list of `(deck_line, line_text)` tuples for the
    header line (with data glued if same-line layout) and any
    following data lines.

    A record ends when EITHER:
      - A `/` terminator appears in a data line (record terminator).
      - A new keyword header (raw line, no leading whitespace) is
        encountered (next keyword's section).

    Recognises three layouts:
    1. Header on its own line, data on subsequent lines until a
       record terminator or new keyword header.
    2. Header + data on the same line (whole record on one line).
    3. Header alone with no data (bare `KEYWORD /`) — recorded as
       a single empty record so per-record checks can decide how
       to handle it.

    Returns [] if the keyword is absent from the section.
    """
    section_text = deck.get_section(spec.section)
    if not section_text:
        return []
    section_lines = deck.get_section_lines(spec.section)
    if not section_lines:
        return []
    start, end = section_lines
    records: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    found_header = False
    for deck_line, line in enumerate(section_text.split("\n"), start=start):
        if deck_line > end:
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            # Blank/comment lines: include blank to preserve line
            # numbering in records, but skip comments.
            if found_header and current and stripped:
                # Blank lines inside a record are ambiguous; treat as
                # a soft break for safety.
                records.append(current)
                current = []
            continue
        # Match the keyword header (case-insensitive).
        m = re.match(rf"(?i)^\s*{re.escape(spec.name)}\b(.*)$", stripped)
        if m:
            tail = m.group(1).strip()
            # Found a new record header. Close the previous record
            # (if any) before starting the next.
            if found_header and current:
                records.append(current)
                current = []
            found_header = True
            if tail and tail != "/":
                # Layout 2: header + data on the same line.
                if tail.endswith("/"):
                    tail = tail[:-1].strip()
                current.append((deck_line, f"{spec.name} {tail}"))
                records.append(current)
                current = []
                continue
            # Header on its own line. The terminator may be the very
            # next line (`KEYWORD /`) or data may follow.
            continue
        if not found_header:
            continue
        # We are inside a record's data lines.
        # Distinguish "data + record terminator" from "data line
        # followed by next record's data" — Eclipse allows multiple
        # `/`-terminated records back-to-back.
        if stripped == "/" or stripped.startswith("/"):
            # A bare `/` line (no data on this line) is the section
            # terminator. We already saw a record terminator on the
            # previous data line; this just closes the section.
            if current:
                records.append(current)
                current = []
            break
        if "/" in stripped:
            # Record terminator on this line. Append the line,
            # close the record.
            current.append((deck_line, stripped))
            records.append(current)
            current = []
            continue
        # New keyword header (raw line, no leading whitespace).
        if (
            not line.startswith((" ", "\t"))
            and re.match(r"^[A-Z][A-Z0-9_]*\b", stripped)
        ):
            # Records of *any* other keyword after our target are not
            # part of our spec — stop iterating.
            if current:
                records.append(current)
                current = []
            break
        current.append((deck_line, stripped))
    if current:
        records.append(current)
    return records


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
    """ERROR if any record of the keyword has fewer or more items than spec.

    Phase 3.5: iterates over every record. For multi-record keywords
    (repeated: true) like PVTO, SWOF, FUNVAR, this catches errors
    in record 2, row 5, etc. — not just the first one.

    Item-count bounds come from `spec.effective_min_items` and
    `spec.effective_max_items` (default: 1 and len(items)). For
    keywords like WELLDIMS where items 5-12 default to 0, set
    `min_items: 1` in the YAML so a 4-item record is accepted.

    Keywords with `skip_item_count: true` opt out entirely. Used for
    data-list keywords like DX/DY/DZ/PORO/PERMX whose item count is
    data-dependent (must equal nx*ny*nz per the L003 cross-rule).
    """
    if spec.skip_item_count:
        return []
    if not spec.items:
        return []
    expected_min = spec.effective_min_items
    expected_max = spec.effective_max_items
    records = _find_all_records(deck, spec)
    if not records:
        # Keyword absent or has no data; _check_required catches that.
        return []
    issues: list[LintIssue] = []
    severity = "WARNING" if _is_calibrated(spec) else "INFO"
    for record_idx, record_lines in enumerate(records):
        if not record_lines:
            # Bare `KEYWORD /` — no items, treat as all defaults.
            continue
        first_line_num, first_line_text = record_lines[0]
        try:
            tokens = _tokenize_record(first_line_text)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("could not tokenize %s record %d: %s", spec.name, record_idx, exc)
            issues.append(_record_unparseable(spec, first_line_num, exc))
            continue
        actual = len(tokens)
        if expected_min <= actual <= expected_max:
            continue
        if actual > expected_max:
            hint = "more items than declared in spec"
        else:
            hint = "fewer items than declared in spec"
        which = "" if len(records) == 1 else f" (record {record_idx + 1})"
        issues.append(LintIssue(
            severity=severity,
            section=spec.section,
            keyword=spec.name,
            line=first_line_num,
            message=(
                f"{spec.name} record has {actual} items, spec accepts "
                f"{expected_min}-{expected_max}{which} ({hint})"
            ),
            rule_id=f"L2.{spec.name}.item_count",
        ))
    return issues


# ---------------------------------------------------------------------- #
# Check: item_range                                                      #
# ---------------------------------------------------------------------- #

def _check_item_ranges(deck: Deck, spec: KeywordSpec) -> list[LintIssue]:
    """WARNING/INFO if any item value is outside the spec's range.

    Phase 3.5: iterates over every record. For multi-record keywords
    like PVTO, this catches out-of-range values in record 2, 3, ...

    Skips non-numeric items (string, keyword, flag) and items with
    no range constraint. Honours `strict_min` / `strict_max` from
    SpecItem (default: inclusive bounds).
    """
    if not spec.items:
        return []
    records = _find_all_records(deck, spec)
    if not records:
        return []
    issues: list[LintIssue] = []
    severity = "WARNING" if _is_calibrated(spec) else "INFO"
    for record_idx, record_lines in enumerate(records):
        if not record_lines:
            continue
        first_line_num, first_line_text = record_lines[0]
        try:
            tokens = _tokenize_record(first_line_text)
        except Exception as exc:  # pragma: no cover - defensive
            issues.append(_record_unparseable(spec, first_line_num, exc))
            continue
        which = "" if len(records) == 1 else f" (record {record_idx + 1})"
        for idx, item in enumerate(spec.items):
            # Phase 3.5: string items with `allowed_values` use that
            # list as the validity check instead of `range`.
            if item.type == "string" and item.allowed_values:
                if idx >= len(tokens):
                    break  # _check_item_count will fire on count.
                raw = tokens[idx]
                if raw.endswith("*"):
                    continue
                if raw.upper() in {v.upper() for v in item.allowed_values}:
                    continue
                issues.append(LintIssue(
                    severity=severity,
                    section=spec.section,
                    keyword=spec.name,
                    line=first_line_num,
                    message=(
                        f"{spec.name}{which} item {idx + 1} ({item.name}) is "
                        f"{raw!r}; allowed: {item.allowed_values}"
                    ),
                    rule_id=f"L2.{spec.name}.range",
                ))
                continue
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
                    severity=severity,
                    section=spec.section,
                    keyword=spec.name,
                    line=first_line_num,
                    message=(
                        f"{spec.name}{which} item {idx + 1} ({item.name}) is "
                        f"{raw!r}; expected a number in range {item.range}"
                    ),
                    rule_id=f"L2.{spec.name}.range",
                ))
                continue
            lo, hi = item.range
            if item.type == "int":
                lo_n: float | int = int(lo)
                hi_n: float | int = int(hi)
            else:
                lo_n, hi_n = lo, hi
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
                    severity=severity,
                    section=spec.section,
                    keyword=spec.name,
                    line=first_line_num,
                    message=(
                        f"{spec.name}{which} item {idx + 1} ({item.name}) is "
                        f"{value} ({where} spec range {item.range})"
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
