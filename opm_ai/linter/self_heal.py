"""Phase 6 — Self-heal library.

Given a deck and a list of LintIssues, propose concrete fixes.
Each fix is mechanically-derivable; the goal is to give the user
one-click resolutions for the most common lint errors.

The library is conservative:
- A fix is only proposed when the rule is on the supported list.
- Each fix carries a confidence score (0.0-1.0). High-confidence
  fixes are mechanically safe (missing terminator); medium are
  heuristic (typo corrections).
- Applying a fix never blocks the verdict — `apply_fix` returns
  the modified deck, and the caller can re-lint to verify.

Initial fix library (see FIX_REGISTRY below):
- L001 (missing terminator):  confidence 1.0 — append '/' to the
  keyword's last data line.
- L016 (unknown keyword, FU_/WU_/L-prefix):  variable confidence
  based on the suggestion:
    - exact typo suggestion from L016:  0.9 (mechanical: take the
      suggested keyword).
    - heuristic FU_/WU_ prefix filter:  1.0 (already excluded by
      classifier — but if we get here, the L016 rule is wrong).
    - other unknown keywords:  0.5 (could be a typo OR a custom
      user keyword).
- L2.<KW>.required:  confidence 0.8 — we know what to add and
  OPM Flow's defaults are documented in the spec notes.
- L2.<KW>.mutex:  confidence 0.5 — which of the pair to keep is a
  modelling decision.

The library is a registry (dict keyed by rule_id) so future
phases can add rules without changing the dispatcher.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue


# ---------------------------------------------------------------------- #
# FixProposal                                                            #
# ---------------------------------------------------------------------- #

@dataclass(frozen=True)
class FixProposal:
    """A proposed fix for a single LintIssue.

    Attributes:
        issue_id: a stable id of the issue this fix targets. We
            use `(rule_id, line, message)` so that the same issue
            (re-linted) maps to the same proposal.
        kind: how the fix rewrites the deck.
        old: the original substring being changed (for diff UI).
        new: the replacement substring.
        confidence: 0.0-1.0. 1.0 = mechanical, 0.5 = heuristic.
        rationale: human-readable reason for the fix.
    """
    issue_id: str
    kind: str  # 'replace_keyword' | 'add_terminator' | 'add_keyword' | 'set_value' | 'remove_keyword'
    old: str
    new: str
    confidence: float
    rationale: str

    def to_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "kind": self.kind,
            "old": self.old,
            "new": self.new,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


def _issue_id(issue: LintIssue) -> str:
    return f"{issue.rule_id}|{issue.line}|{issue.message}"


# ---------------------------------------------------------------------- #
# Individual fixers                                                      #
# ---------------------------------------------------------------------- #

def fix_L001_missing_terminator(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    """Append '/' to the keyword's last data line.

    L001 fires on the keyword header line, but the terminator must
    be appended to the LAST data line of that keyword's record —
    not to the header itself. We walk forward from the issue's
    line until we hit either:
      - a line that already ends with '/' (this record is fine;
        return None — the issue must be on a different record).
      - a new keyword header (this record never closed; nothing
        to terminate).
      - the end of the section / deck (this record never closed).
    """
    if issue.line is None:
        return None
    lines = deck_text.split("\n")
    if not (1 <= issue.line <= len(lines)):
        return None
    # Walk forward from issue.line+1 looking for the data line
    # that needs the terminator.
    target_idx = None
    for idx in range(issue.line, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith("--"):
            continue
        # Bare terminator means there's nothing to terminate.
        if stripped == "/":
            return None
        # A new keyword header means we passed the record without
        # finding data — unusual, but safe.
        if (
            not lines[idx].startswith((" ", "\t"))
            and re.match(r"^[A-Z][A-Z0-9_]*\b", stripped)
        ):
            return None
        # Otherwise this is the data line — append '/' to it.
        if stripped.endswith("/"):
            # Already terminated — return None.
            return None
        target_idx = idx
        break
    if target_idx is None:
        return None
    line = lines[target_idx]
    new_line = line.rstrip() + " /"
    return FixProposal(
        issue_id=_issue_id(issue),
        kind="add_terminator",
        old=line,
        new=new_line,
        confidence=1.0,
        rationale=(
            f"Line {target_idx + 1} (the keyword '{issue.keyword}' "
            f"record's last data line) is missing the record "
            f"terminator '/' that OPM Flow expects."
        ),
    )


def fix_L016_unknown_keyword(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    """Replace an unknown keyword with the L016 'did you mean' suggestion.

    L016's message looks like:
        "Unknown keyword 'WELSECS'; did you mean 'WELSPECS'?"
    We parse the suggested replacement. If absent, no fix is proposed.
    """
    msg = issue.message
    suggestion_match = re.search(r"did you mean '([^']+)'\?", msg)
    if not suggestion_match:
        # No suggestion available — the fix is unsafe (could be a
        # user-defined keyword).
        return None
    suggested = suggestion_match.group(1)
    if issue.keyword is None or issue.line is None:
        return None
    lines = deck_text.split("\n")
    if not (1 <= issue.line <= len(lines)):
        return None
    line = lines[issue.line - 1]
    # Replace the keyword token exactly (case-sensitive to match the
    # existing casing; the catalogue is upper-case).
    new_line = re.sub(
        rf"\b{re.escape(issue.keyword)}\b",
        suggested,
        line,
        count=1,
    )
    if new_line == line:
        return None
    return FixProposal(
        issue_id=_issue_id(issue),
        kind="replace_keyword",
        old=line,
        new=new_line,
        confidence=0.9,
        rationale=(
            f"L016 suggested '{suggested}' as a correction for "
            f"'{issue.keyword}'. The suggestion comes from edit "
            f"distance against the keyword catalogue."
        ),
    )


def fix_L2_required(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    """Insert a minimal valid record for a missing required keyword.

    Currently supports a small set of keywords with documented
    OPM Flow defaults. The set is intentionally conservative —
    most required keywords need context (DIMENS needs the cell
    count, which is ambiguous). The library returns None for any
    keyword we don't know how to default.
    """
    rule_id = issue.rule_id or ""
    # Parse: L2.<KEYWORD>.required
    parts = rule_id.split(".")
    if len(parts) != 3:
        return None
    _, kw, check = parts
    if check != "required":
        return None
    kw = kw.upper()
    # Default snippets — verified against OPM Flow manual.
    defaults = {
        "WELLDIMS": "WELLDIMS\n  1 1 1 1 0 0 0 0 0 0 0 0 /",
        "DIMENS": None,  # can't default — needs context
        "TABDIMS": "TABDIMS\n  1 1 1 1 1 0 0 0 /",
        "ENDSCALE": "ENDSCALE\n  'NODIR' 'NODIR' 1 20 /",
        "WELSPECS": None,  # can't default — needs well name
        "PORO": None,      # can't default
        "PERMX": None,     # can't default
        "DX": None,
        "DY": None,
        "DZ": None,
    }
    snippet = defaults.get(kw)
    if snippet is None:
        return None
    return FixProposal(
        issue_id=_issue_id(issue),
        kind="add_keyword",
        old="",
        new=snippet,
        confidence=0.8,
        rationale=(
            f"OPM Flow requires {kw} in the {issue.section} section. "
            f"Inserting a default-value record that matches the OPM "
            f"Flow manual. Verify the values match your model."
        ),
    )


def fix_L2_mutex(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    """Remove one of the mutually-exclusive keywords.

    Defaults to removing the partner keyword (the one named in the
    message), keeping the original. Lower confidence because the
    choice between the pair is a modelling decision.
    """
    msg = issue.message
    partner_match = re.search(r"with (\w+):", msg)
    if not partner_match:
        return None
    partner = partner_match.group(1)
    if issue.line is None:
        return None
    lines = deck_text.split("\n")
    if not (1 <= issue.line <= len(lines)):
        return None
    # Walk forward from issue.line to find the partner keyword.
    block_start = None
    block_end = None
    for idx, line in enumerate(lines):
        stripped = line.strip().upper()
        if stripped.startswith(partner):
            if block_start is None:
                block_start = idx
        if block_start is not None and idx > block_start and (
            re.match(r"^[A-Z][A-Z0-9_]*\b", stripped)
            and not stripped.startswith(partner)
            and not stripped.startswith("/")
        ):
            block_end = idx
            break
    if block_start is None:
        return None
    if block_end is None:
        block_end = len(lines)
    block = lines[block_start:block_end]
    return FixProposal(
        issue_id=_issue_id(issue),
        kind="remove_keyword",
        old="\n".join(block),
        new="",
        confidence=0.5,
        rationale=(
            f"Removing the {partner} keyword block to resolve the "
            f"mutual-exclusion violation with {issue.keyword}. "
            f"This is a modelling decision — verify which of the "
            f"two keywords matches your fluid model."
        ),
    )


# ---------------------------------------------------------------------- #
# Registry                                                              #
# ---------------------------------------------------------------------- #

def fix_L2_required_dispatcher(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    return fix_L2_required(issue, deck_text)


# Dispatch table keyed by rule_id pattern. Order matters: more
# specific patterns first.
FIX_REGISTRY: list[tuple[str, Callable[[LintIssue, str], Optional[FixProposal]]]] = [
    ("L001", fix_L001_missing_terminator),
    ("L016", fix_L016_unknown_keyword),
    # L2.<KW>.required via dispatcher
    (r"^L2\.[A-Z0-9_]+\.required$", fix_L2_required),
    (r"^L2\.[A-Z0-9_]+\.mutex$", fix_L2_mutex),
]


def propose_fix(issue: LintIssue, deck_text: str) -> Optional[FixProposal]:
    """Return a FixProposal for the given issue, or None if unsupported."""
    for pattern, fixer in FIX_REGISTRY:
        if pattern.startswith("^") or "*" in pattern or "[" in pattern:
            if re.match(pattern, issue.rule_id or ""):
                return fixer(issue, deck_text)
        else:
            if issue.rule_id == pattern:
                return fixer(issue, deck_text)
    return None


def propose_fixes(deck_path: Path, issues: list[LintIssue]) -> list[FixProposal]:
    """Propose fixes for every fixable issue on a deck."""
    try:
        deck_text = deck_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    out: list[FixProposal] = []
    for issue in issues:
        proposal = propose_fix(issue, deck_text)
        if proposal is not None:
            out.append(proposal)
    return out


# ---------------------------------------------------------------------- #
# Apply                                                                  #
# ---------------------------------------------------------------------- #

def apply_fix(deck_text: str, fix: FixProposal) -> str:
    """Apply a single fix and return the modified deck text.

    The fix is applied by string substitution: `fix.old` is
    replaced with `fix.new`. For `add_keyword` (where old=""), the
    fix is appended at the end of the relevant section. We don't
    try to be smart about insertion location — the verification
    step (re-lint) catches the cases where it doesn't work.
    """
    if fix.kind == "add_terminator" and fix.old != "":
        return deck_text.replace(fix.old, fix.new, 1)
    if fix.kind == "replace_keyword" and fix.old != "":
        return deck_text.replace(fix.old, fix.new, 1)
    if fix.kind == "remove_keyword" and fix.old != "":
        return deck_text.replace(fix.old, "", 1)
    if fix.kind == "add_keyword":
        # Insert at end of section. The fix proposal carries the
        # snippet to add; we need the section name to know where to
        # put it. The caller can refine this — for now we append
        # to end of deck and let the user move it. (Phase 6.5 will
        # add proper section insertion.)
        return deck_text.rstrip() + "\n\n" + fix.new + "\n"
    if fix.kind == "set_value":
        # Same as replace_keyword for now.
        return deck_text.replace(fix.old, fix.new, 1)
    return deck_text


def apply_fixes(deck_path: Path, fixes: list[FixProposal]) -> str:
    """Apply a list of fixes sequentially. Returns the modified text."""
    text = deck_path.read_text(encoding="utf-8", errors="replace")
    for fix in fixes:
        text = apply_fix(text, fix)
    return text


# ---------------------------------------------------------------------- #
# Verification                                                           #
# ---------------------------------------------------------------------- #

def verify_fix(
    deck_path: Path,
    fix: FixProposal,
    baseline_issue_count: int,
) -> bool:
    """Apply a fix and re-lint. Return True if the issue count dropped.

    This is the safety net: even a 1.0-confidence fix can be wrong
    (the linter can have its own bugs). A re-lint that finds fewer
    issues is strong evidence the fix worked.
    """
    from opm_ai.linter.linter import lint_deck
    original = deck_path.read_text(encoding="utf-8", errors="replace")
    modified = apply_fix(original, fix)
    # Write to a temp file and re-lint.
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".DATA", delete=False, encoding="utf-8"
    ) as f:
        f.write(modified)
        tmp_path = Path(f.name)
    try:
        new_result = lint_deck(tmp_path)
        new_count = len(new_result.issues)
    except Exception:
        return False
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass
    return new_count < baseline_issue_count