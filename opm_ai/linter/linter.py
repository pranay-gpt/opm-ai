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