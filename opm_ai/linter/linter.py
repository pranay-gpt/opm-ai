"""Linter orchestrator - runs deck through rule engine and returns LintResult."""

from pathlib import Path
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue, LintResult
from opm_ai.linter.rules.registry import run_all


def lint_deck(deck_path: Path) -> LintResult:
    """Lint an Eclipse deck file.

    Args:
        deck_path: Path to .DATA deck file

    Returns:
        LintResult with issues, errors, warnings, and pass/fail status
    """
    deck = Deck(deck_path)

    # Run all rules
    issues = run_all(deck)

    # Add missing required sections as ERRORs
    required_sections = ["RUNSPEC", "GRID", "SCHEDULE"]
    for section in required_sections:
        if not deck.has_section(section):
            issues.append(LintIssue(
                severity="ERROR",
                section=section,
                keyword="SECTION",
                line=None,
                message=f"Required section '{section}' is missing",
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