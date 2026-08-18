"""Linter orchestrator - runs deck through rule engine and returns LintResult."""

import re
from pathlib import Path
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue, LintResult
from opm_ai.linter.rules.registry import run_all


# Process-local cache of parsed Decks, keyed by (path, mtime). Repeated
# lints of the same file on a hot path (editor save -> lint -> render
# loop) used to re-parse the entire deck on every call; the cache turns
# that into a stat() + dict lookup. The Deck instance is the only thing
# the rules consume, so the cached object can be returned directly.
_DECK_CACHE: dict[tuple[str, float], Deck] = {}
_DECK_CACHE_MAX = 8


def _get_deck(deck_path: Path) -> Deck:
    """Return a parsed Deck, reusing a cached one if (path, mtime)
    matches. The cache is bounded to keep long-running processes from
    holding every deck they ever saw."""
    # Use st_mtime_ns (nanosecond integer) so back-to-back writes on a
    # fast filesystem still register as a new key. st_mtime is
    # float-second and can collide within a single test.
    key = (str(deck_path), deck_path.stat().st_mtime_ns)
    cached = _DECK_CACHE.get(key)
    if cached is not None:
        return cached
    deck = Deck(deck_path)
    if len(_DECK_CACHE) >= _DECK_CACHE_MAX:
        # Simple eviction: drop the oldest insertion. dicts preserve
        # insertion order, so next(iter(...)) is the oldest key.
        _DECK_CACHE.pop(next(iter(_DECK_CACHE)))
    _DECK_CACHE[key] = deck
    return deck


def clear_deck_cache() -> None:
    """Drop every cached Deck. Tests use this to assert parse counts."""
    _DECK_CACHE.clear()


def lint_deck(deck_path: Path) -> LintResult:
    """Lint an Eclipse deck file.

    Args:
        deck_path: Path to .DATA deck file

    Returns:
        LintResult with issues, errors, warnings, and pass/fail status
    """
    deck = _get_deck(deck_path)

    # Run all rules
    issues = run_all(deck)

    # Add missing required sections as ERRORs. Decks that INCLUDE other files
    # may receive whole sections from them (e.g. SPE5CASE1 pulls GRID/SCHEDULE
    # from SPE5.BASE); the v1 linter does not resolve includes, so downgrade
    # to WARNING in that case instead of false-positive blocking.
    try:
        deck_text = Path(deck_path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        deck_text = ""
    has_include = bool(re.search(r"(?im)^\s*INCLUDE\b", deck_text))

    required_sections = ["RUNSPEC", "GRID", "SCHEDULE"]
    for section in required_sections:
        if not deck.has_section(section):
            issues.append(LintIssue(
                severity="WARNING" if has_include else "ERROR",
                section=section,
                keyword="SECTION",
                line=None,
                message=(
                    f"Required section '{section}' is missing"
                    + (" from this file (may come from an INCLUDE)" if has_include else "")
                ),
                rule_id="L015" if section == "RUNSPEC" else f"L{section}"
            ))

    # Create result
    result = LintResult(
        deck_path=str(deck_path),
        issues=issues
    )

    # Optional LLM enhancement - graceful degradation.
    # Never flips `passed`; only fills lint_summary when a provider is available.
    try:
        from opm_ai.llm.client import LLMClient
        client = LLMClient()
        if client.available:
            summary = client.summarize_issues(issues)
            if summary:
                result.lint_summary = summary
    except Exception:
        # LLM unavailable or error - continue with rule-only result
        pass

    return result


def lint_deck_v2(deck_path: Path) -> "v2.LintResult":
    """Run the v2 linter on a deck file.

    The v2 linter is the redesigned (Phase 4) linter with cross-
    reference, dimension-consistency, requires, section, and OPM-
    Flow-specific rules. It operates on its own AST and does not
    share a symbol table with L1.

    This is the entry point used by tests/integration/test_corpus_clean.py
    and the planned coexistence path (lint_deck_combined).

    Args:
        deck_path: Path to a .DATA deck file.

    Returns:
        v2.LintResult with v2.LintIssue dataclass instances.

    Note:
        The v2 linter is currently read-only — it does not write to
        the file. The path is read for the source_file attribution
        and to detect INCLUDE/IMPORT paths.
    """
    from opm_ai.linter.v2 import parser as v2_parser
    from opm_ai.linter.v2.resolver import resolve_deck
    from opm_ai.linter.v2.validator import LintResult as V2LintResult

    text = Path(deck_path).read_text(encoding="utf-8", errors="replace")
    deck = v2_parser.parse_file(text, source_file=deck_path)
    resolve_deck(deck)
    return V2LintResult.from_deck(deck) if hasattr(V2LintResult, "from_deck") else _v2_validate(deck)


def _v2_validate(deck):
    """Internal: validate via v2.validator.validate()."""
    from opm_ai.linter.v2.validator import validate
    return validate(deck)


def lint_deck_combined(deck_path: Path) -> LintResult:
    """Run L1 then v2, deduplicate, return combined LintResult.

    Both linters run on the same deck file. Issues are deduplicated
    by (rule_id, line, message-prefix) so identical diagnostics from
    both engines don't double-count. v2 issues are converted to L1
    LintIssue shape for a single uniform output. v2 issues whose rule
    code has a registered FixProposal also carry a `fix_proposal`
    summary so the UI can offer an "Apply Fix" button per issue.

    Args:
        deck_path: Path to a .DATA deck file.

    Returns:
        LintResult with issues from both linters, deduplicated. Each
        issue from a v2 rule with a registered FixProposal has a
        populated `fix_proposal`.
    """
    from opm_ai.linter.v2.validator import LintIssue as V2Issue, Severity as V2Severity

    # Run L1 (existing).
    l1_result = lint_deck(deck_path)

    # Run v2. Best-effort: if v2 fails (parse error, missing file),
    # return L1 alone.
    try:
        v2_result = lint_deck_v2(deck_path)
    except Exception as e:  # pragma: no cover - v2 failures should be visible
        l1_result.issues.append(LintIssue(
            severity="WARNING",
            keyword="L200",
            line=None,
            message=f"v2 linter failed: {type(e).__name__}: {e}",
            rule_id="L200",
        ))
        return l1_result

    # Read deck text once so each FixProposal can be computed against
    # the same source. Failures here are non-fatal — we just skip
    # attaching proposals (L1 issues still surface as before).
    deck_text: Optional[str] = None
    try:
        deck_text = deck_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass

    # Convert v2 issues to L1 shape and append, deduplicating.
    seen_keys: set[tuple] = set()
    for issue in l1_result.issues:
        seen_keys.add(_dedup_key(issue))

    for v2i in v2_result.issues:
        l1i = _convert_v2_issue(v2i, deck_text)
        if _dedup_key(l1i) not in seen_keys:
            l1_result.issues.append(l1i)
            seen_keys.add(_dedup_key(l1i))

    return l1_result


def _convert_v2_issue(v2i, deck_text: Optional[str] = None) -> LintIssue:
    """Convert a v2 LintIssue (dataclass) to the L1 Pydantic shape.

    The two shapes diverge in:
    - L1 has `section` (str | None); v2 has `source_file` (Path | None).
    - L1 has `rule_id` (str | None); v2 has `code` (int).
    - L1 `severity` is a Literal["ERROR","WARNING","INFO"]; v2 is an Enum
      with the same string values.

    Conversion is lossless on the consumer-visible fields (rule_id,
    severity, message, line). The v2 `source_file` is dropped — the
    file is the same one we just parsed, so this is redundant.
    """
    section = None
    if v2i.keyword is not None:
        kw_section = getattr(v2i.keyword, "section", None)
        if kw_section is not None:
            # v2 Keyword has .section: Section; Section has .name: SectionName (str Enum).
            section_name = getattr(kw_section, "name", None)
            if section_name is not None:
                section = getattr(section_name, "value", section_name)
    keyword_name = getattr(v2i.keyword, "name", None) if v2i.keyword else None
    rule_id = f"L{v2i.code}"

    # Attach a FixProposalView if this rule has a registered proposal
    # function and it succeeds against the current deck text. Failure
    # to produce a proposal is non-fatal — the issue still surfaces,
    # just without an Apply Fix button.
    fix_proposal = None
    if deck_text is not None:
        try:
            from opm_ai.linter.v2.fix_proposals import propose_fix
            from opm_ai.linter.models import FixProposalView

            proposal = propose_fix(v2i, deck_text)
            if proposal is not None:
                fix_proposal = FixProposalView(
                    rule_id=rule_id,
                    description=proposal.description,
                    original_value=proposal.original_value,
                    new_value=proposal.new_value,
                )
        except Exception:
            # Proposal failures must never break lint output.
            pass

    return LintIssue(
        severity=v2i.severity.value,
        section=section,
        keyword=keyword_name,
        line=v2i.source_line,
        message=v2i.message,
        rule_id=rule_id,
        fix_proposal=fix_proposal,
    )


def _dedup_key(issue: LintIssue) -> tuple:
    """Key for deduplicating L1 vs v2 issues.

    Two issues from different linters count as the same diagnostic
    if they fire on the same line with the same rule code and a
    matching message prefix (first 40 chars).

    A loose prefix avoids false negatives where L1 says
    "WELSPECS missing" and v2 says "well 'W1' is not declared" —
    these are different rules about the same problem and should
    not be deduped.
    """
    line = issue.line if issue.line is not None else -1
    rule = issue.rule_id or ""
    msg = (issue.message or "")[:40]
    return (rule, line, msg)