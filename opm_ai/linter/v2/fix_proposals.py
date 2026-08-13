"""Fix proposals for v2 linter issues.

Each LintIssue describes a defect. A `FixProposal` is a concrete
patch that, if applied to the deck, would address the issue. The
calibration loop applies proposals and measures, via `flow
--enable-dry-run=true`, whether the patched deck still passes Flow's
acceptance check. Successful proposals become the basis of the
self-heal agent's confidence scores.

Design principles
-----------------

1. **Mechanical, deterministic.** Every proposal is a text-level
   arithmetic change. No inference, no guessing, no LLM. We start
   with rules where the fix is obvious:

   - L232 WELLDIMS MAXWELLS exceeded → bump MAXWELLS to actual + 1
   - L234 REGDIMS NTFIP exceeded       → bump NTFIP to max-region + 1
   - L231 TABDIMS NSSFUN exceeded      → bump NSSFUN to satur-region-count + 1

   Rules that need semantic judgment (L202 wrong item count, L241
   missing required keyword) are NOT implemented yet. Adding them
   requires structured guessing that's outside the calibration loop's
   remit.

2. **One proposal per (issue, rule).** The proposal function is
   pure: (LintIssue, deck_text) → FixProposal | None. The runner
   applies it, captures diff, runs oracle, records. We do not chain
   multiple proposals per deck in this phase — single-fix isolation
   is what the calibration report needs.

3. **Text-level patches.** We use string replacement on the deck
   text, not AST mutation. This keeps the proposal isolatable and
   testable, and ensures the patch is what the user will see in a
   UI diff. The text replacement is anchored on the LintIssue's
   source_file + source_line and the keyword's first record line.

How a proposal is applied
-------------------------

Given a LintIssue for rule L232 with message:
    "WELLDIMS MAXWELLS=4 but 5 wells declared via WELSPECS"

The proposal function:
1. Reads the LintIssue.keyword to find the WELLDIMS Keyword node.
2. Locates the line in the source text corresponding to the first
   record's items (which is where the integers live).
3. Replaces the first integer on that line with `actual_wells + 1`.
4. Returns a FixProposal with the diff.

If the line cannot be located (the source file changed since
parsing, the keyword is at a different position, etc.), the
proposal returns None and the calibration record is logged as
`proposal_skipped: true`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .ast import Keyword
from .validator import LintIssue


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FixProposal:
    """A concrete patch for a single LintIssue.

    Attributes:
        rule_code: The LintIssue code (231, 232, 234, ...).
        issue_keyword: The Keyword node that triggered the issue.
            Used for source attribution.
        original_text: The proposed-deck text BEFORE the patch.
        patched_text: The proposed-deck text AFTER the patch.
        description: Human-readable summary of what changed
            (e.g. "WELLDIMS line 12: MAXWELLS 4 -> 6").
        original_value: The value that was replaced (e.g. "4").
        new_value: The value that replaced it (e.g. "6").
    """

    rule_code: int
    issue_keyword: Optional[Keyword]
    original_text: str
    patched_text: str
    description: str
    original_value: str
    new_value: str

    def apply(self) -> str:
        """Return the patched text. The dataclass is immutable; this
        is a convenience accessor."""
        return self.patched_text

    def diff_lines(self) -> tuple[list[str], list[str]]:
        """Return (removed_lines, added_lines) for a simple diff display.

        Both are empty if original_text == patched_text (no change).
        Uses whitespace-token-anchored matching so that "4" in the
        middle of "4 5 6 7 8 /" is correctly identified as the
        original value only when the new value is not also a token.
        """
        old_lines = self.original_text.splitlines()
        new_lines = self.patched_text.splitlines()
        if old_lines == new_lines:
            return ([], [])
        # Identify changed lines by token presence.
        old_match = []
        new_match = []
        old_token = self.original_value
        new_token = self.new_value
        for line in old_lines:
            tokens = set(line.split())
            if old_token in tokens and new_token not in tokens:
                old_match.append(line)
        for line in new_lines:
            tokens = set(line.split())
            if new_token in tokens and old_token not in tokens:
                new_match.append(line)
        return (old_match, new_match)


# ---------------------------------------------------------------------------
# Proposal helpers
# ---------------------------------------------------------------------------

def _read_deck_text(issue: LintIssue, fallback_text: str) -> str:
    """Resolve the deck text from the issue's source_file or fallback.

    If the issue has a source_file that exists on disk, read it.
    Otherwise use the fallback_text the caller passed in. This lets
    the calibration runner use the in-memory deck text from the
    orchestrator, while unit tests can pass arbitrary text.
    """
    if issue.source_file is not None:
        try:
            path = Path(issue.source_file)
            if path.exists() and path.is_file():
                return path.read_text(errors="replace")
        except OSError:
            pass
    return fallback_text


def _split_record_line(text: str, line_idx: int) -> Optional[list[str]]:
    """Split a single record line into whitespace-separated tokens.

    Returns None if line_idx is out of range or the line is empty.
    We return strings (not Tokens) because we're doing text-level
    replacement and don't need to re-parse.
    """
    if line_idx < 0 or line_idx >= len(text.splitlines()):
        return None
    line = text.splitlines()[line_idx]
    tokens = line.split()
    if not tokens:
        return None
    return tokens


def _replace_int_value_in_line(
    text: str,
    line_idx: int,
    old_value: str,
    new_value: int,
) -> Optional[str]:
    """Replace the integer `old_value` with `new_value` on the line at line_idx.

    0-indexed. Returns the new text, or None if the line is empty or
    `old_value` doesn't appear as an integer token on the line.

    This is preferred over `_replace_int_at_line` for capacity fixes
    because the keyword header (WELLDIMS, REGDIMS, TABDIMS, EQLDIMS)
    is sometimes on the same line as the items and sometimes on the
    preceding line. We anchor on the value itself, not the column.

    Only the FIRST occurrence of `old_value` on the line is replaced.
    If the line has multiple identical integers (e.g. WELLDIMS
    `4 4 4 4 4 /`), the first one is the right slot for capacity
    increases (item 0 = MAXWELLS for WELLDIMS).
    """
    lines = text.splitlines(keepends=True)
    if line_idx < 0 or line_idx >= len(lines):
        return None
    line = lines[line_idx]
    # Find the first whitespace-separated token equal to old_value.
    # Use a regex to find the int token at the column position.
    pattern = re.compile(r"\S+")
    new_line = None
    for m in pattern.finditer(line):
        if m.group() == old_value:
            new_line = line[:m.start()] + str(new_value) + line[m.end():]
            break
    if new_line is None:
        return None
    lines[line_idx] = new_line
    return "".join(lines)


def _replace_int_at_line(
    text: str,
    line_idx: int,
    column_idx: int,
    new_value: int,
) -> Optional[str]:
    """Replace the integer at (line_idx, column_idx) with new_value.

    Both 0-indexed. Returns the new text, or None if the line is
    malformed (can't find a token at column_idx) or the token at
    column_idx is not an integer.

    Preserves all whitespace and any prior tokens on the line.
    """
    lines = text.splitlines(keepends=True)
    if line_idx < 0 or line_idx >= len(lines):
        return None
    line = lines[line_idx]
    tokens = line.split()
    if column_idx < 0 or column_idx >= len(tokens):
        return None
    target = tokens[column_idx]
    # Require the token to be an integer so we don't accidentally
    # replace a keyword name.
    try:
        int(target)
    except ValueError:
        return None
    # Replace the *first* occurrence of the integer on the line.
    # `line.split()` collapses whitespace, so we must find the actual
    # position in the original line. Use a regex to find the int
    # token at the column position.
    #
    # We rebuild the line by splitting on whitespace runs but
    # preserving the original separator pattern.
    pattern = re.compile(r"\S+")
    matches = list(pattern.finditer(line))
    if column_idx >= len(matches):
        return None
    target_match = matches[column_idx]
    if target_match.group() != target:
        return None
    new_line = (
        line[:target_match.start()] + str(new_value) + line[target_match.end():]
    )
    lines[line_idx] = new_line
    return "".join(lines)


def _record_line_index(keyword: Keyword) -> int:
    """Return the 0-indexed line of the keyword's first record's first item.

    Keyword.header_token.line is 1-indexed and points to the line where
    the keyword name appears. For FIXED-size keywords (TABDIMS, WELLDIMS,
    REGDIMS, EQLDIMS), the record items are on the SAME line as the
    header. For LIST/ARRAY keywords, items could be on a different line.
    We use the first item's line as the canonical "value line", which
    is correct for all the rules we currently implement (L231/L232/L234
    all target FIXED-size keywords).
    """
    if keyword.records and keyword.records[0].items:
        first_item = keyword.records[0].items[0]
        # Token.line is 1-indexed; convert to 0-indexed.
        return first_item.line - 1
    # Fallback: keyword header line.
    return keyword.header_token.line - 1


# ---------------------------------------------------------------------------
# Per-rule proposal functions
# ---------------------------------------------------------------------------

def propose_l232_fix(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    """L232: WELLDIMS MAXWELLS exceeded → bump to actual_wells + 1.

    Message format: 'WELLDIMS MAXWELLS=<N> but <M> wells declared via WELSPECS'
    """
    if issue.code != 232 or issue.keyword is None:
        return None
    text = _read_deck_text(issue, deck_text)
    m = re.search(r"MAXWELLS=(\d+) but (\d+) wells declared", issue.message)
    if m is None:
        return None
    original_value = m.group(1)
    actual_wells = int(m.group(2))
    new_value = actual_wells + 1
    if int(original_value) >= new_value:
        # No fix is meaningful (already big enough).
        return None

    line_idx = _record_line_index(issue.keyword)
    patched = _replace_int_value_in_line(text, line_idx, original_value, new_value)
    if patched is None:
        return None

    return FixProposal(
        rule_code=232,
        issue_keyword=issue.keyword,
        original_text=text,
        patched_text=patched,
        description=(
            f"WELLDIMS line {line_idx + 1}: MAXWELLS "
            f"{original_value} -> {new_value}"
        ),
        original_value=original_value,
        new_value=str(new_value),
    )


def propose_l234_fix(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    """L234: REGDIMS NTFIP exceeded → bump to max_fipnum + 1.

    Message format: 'REGDIMS NTFIP=<N> but max FIPNUM region is <M> ...'
    """
    if issue.code != 234 or issue.keyword is None:
        return None
    text = _read_deck_text(issue, deck_text)
    m = re.search(r"NTFIP=(\d+) but max FIPNUM region is (\d+)", issue.message)
    if m is None:
        return None
    original_value = m.group(1)
    max_region = int(m.group(2))
    new_value = max_region + 1
    if int(original_value) >= new_value:
        return None

    line_idx = _record_line_index(issue.keyword)
    patched = _replace_int_value_in_line(text, line_idx, original_value, new_value)
    if patched is None:
        return None

    return FixProposal(
        rule_code=234,
        issue_keyword=issue.keyword,
        original_text=text,
        patched_text=patched,
        description=(
            f"REGDIMS line {line_idx + 1}: NTFIP "
            f"{original_value} -> {new_value}"
        ),
        original_value=original_value,
        new_value=str(new_value),
    )


def propose_l231_fix(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    """L231: TABDIMS NSSFUN exceeded → bump NSSFUN to satur-region-count + 1.

    Message format: 'TABDIMS NSSFUN=<N> allows up to <N+1> ... but <M> found'
    TABDIMS is 10 ints: NTSFUN NPPVF NSSFUN NTPVT NTREG NTROC ...
    NSSFUN is column index 2 (0-indexed).

    Because NSSFUN's value can collide with NTSFUN (column 0) or NPPVF
    (column 1), we use column-indexed replacement anchored on the
    record's first item (NOT the keyword header line — items may be
    on the next line).
    """
    if issue.code != 231 or issue.keyword is None:
        return None
    text = _read_deck_text(issue, deck_text)
    m = re.search(r"NSSFUN=(\d+) allows up to \d+ .*? but (\d+) found", issue.message)
    if m is None:
        return None
    original_value = m.group(1)
    sat_region_count = int(m.group(2))
    new_value = sat_region_count + 1
    if int(original_value) >= new_value:
        return None

    line_idx = _record_line_index(issue.keyword)
    # NSSFUN is column 2 (0-indexed) in TABDIMS. Unlike L232/L234,
    # we use column-indexed replacement because the value at column 2
    # can collide with column 0 (NTSFUN) or column 1 (NPPVF).
    patched = _replace_int_at_line(text, line_idx, 2, new_value)
    # If the keyword is on the same line as the items, column 2 is
    # actually column 3 (the keyword is column 0). Fall back to
    # value-based replacement if column-indexed fails.
    if patched is None:
        patched = _replace_int_value_in_line(
            text, line_idx, original_value, new_value
        )
    if patched is None:
        return None

    return FixProposal(
        rule_code=231,
        issue_keyword=issue.keyword,
        original_text=text,
        patched_text=patched,
        description=(
            f"TABDIMS line {line_idx + 1}: NSSFUN "
            f"{original_value} -> {new_value}"
        ),
        original_value=original_value,
        new_value=str(new_value),
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Map rule code → proposal function. Rules without an entry here
# are simply not fixable by the calibration loop in this phase.
PROPOSAL_REGISTRY: dict[int, "callable"] = {
    231: propose_l231_fix,
    232: propose_l232_fix,
    234: propose_l234_fix,
}


def propose_fix(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    """Dispatch to the right proposal function for this issue.

    Returns None if the rule has no registered proposal function, or
    if the proposal function itself returns None (e.g. unable to
    locate the source line).
    """
    fn = PROPOSAL_REGISTRY.get(issue.code)
    if fn is None:
        return None
    return fn(issue, deck_text)


__all__ = [
    "FixProposal",
    "PROPOSAL_REGISTRY",
    "propose_fix",
    "propose_l231_fix",
    "propose_l232_fix",
    "propose_l234_fix",
]
