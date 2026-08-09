"""Linter orchestrator - runs deck through rule engine and returns LintResult."""

import re
from pathlib import Path
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue, LintResult
from opm_ai.linter.rules.registry import run_all
from opm_ai.linter.spec import KeywordSpec, load_spec
from opm_ai.linter.validator import validate


# Process-local cache of parsed Decks, keyed by (path, mtime). Repeated
# lints of the same file on a hot path (editor save -> lint -> render
# loop) used to re-parse the entire deck on every call; the cache turns
# that into a stat() + dict lookup. The Deck instance is the only thing
# the rules consume, so the cached object can be returned directly.
_DECK_CACHE: dict[tuple[str, float], Deck] = {}
_DECK_CACHE_MAX = 8

# Process-local cache for the loaded YAML specs. Same lifecycle as
# _DECK_CACHE: load once, reuse. The spec_dir is shipped with the
# package so we resolve relative to the linter module, not the
# working directory. If a YAML file is malformed, load_spec raises
# at first call; we swallow it and return {} so the linter degrades
# gracefully (the L1/L3 rules still fire; only L2 is silently off).
_SPEC_DIR = Path(__file__).parent / "spec"
_SPEC_CACHE: dict[str, KeywordSpec] | None = None


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


def _get_specs() -> dict[str, KeywordSpec]:
    """Lazy-load and cache the YAML specs.

    On a malformed spec, return {} and log the error so the L2 layer
    silently disables. The L1/L3 rules continue to fire; the user sees
    a warning in logs rather than a 500 from the API.
    """
    global _SPEC_CACHE
    if _SPEC_CACHE is not None:
        return _SPEC_CACHE
    try:
        _SPEC_CACHE = load_spec(_SPEC_DIR)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "spec load failed (%s: %s); L2 layer disabled",
            type(exc).__name__, exc,
        )
        return {}
    return _SPEC_CACHE


def clear_spec_cache() -> None:
    """Drop the cached YAML specs. Tests use this to reload specs after
    they change them on disk.

    Tests that modify `opm_ai/linter/spec/*.yaml` mid-test should call
    this before re-linting; otherwise the L2 layer sees stale specs.
    """
    global _SPEC_CACHE
    _SPEC_CACHE = None


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

    # Run L1/L3 rules (existing 18 rules)
    issues = run_all(deck)
    # Run L2 schema-driven checks (Phase 3 of the linter-redesign plan).
    # The validator consumes the hand-curated YAML specs in
    # opm_ai/linter/spec/ and emits `L2.<KEYWORD>.<CHECK>` issues.
    issues.extend(validate(deck, _get_specs()))

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

    # Phase 5: populate `explanation` on every issue. The frontend
    # then renders the Markdown next to each lint error. The
    # explainer is opt-out friendly — failures degrade to None
    # rather than raising, so a malformed explanation never blocks
    # the lint verdict.
    try:
        from opm_ai.linter.explainer import explain_issue
        explained = [explain_issue(i) for i in result.issues]
        result = result.model_copy(update={"issues": explained})
    except Exception:
        # Explainer failure must not change the verdict; ignore.
        pass

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