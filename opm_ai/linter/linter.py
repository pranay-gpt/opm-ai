# opm_ai/linter/linter.py
"""
AI Deck Linter — two-stage pipeline:

  Stage 1 (fast, offline): static rule engine in rules.py
  Stage 2 (LLM):           Groq LLM adds plain-English narrative + fix snippets

The LLM stage is optional. If GROQ_API_KEY is not set, the linter
still returns full structured diagnostics from the rule engine alone.
"""
import os
import json
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

from .models import DeckDiagnostic, DiagnosticSeverity, LintResult
from .rules import RULES
from ..runner.models import CrashReport

load_dotenv()

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_LLM_MODEL    = "llama-3.3-70b-versatile"


# ── Public API ───────────────────────────────────────────────────────────────

def lint_deck(
    deck_text: str,
    crash_reports: list[CrashReport] | None = None,
    use_llm: bool = True,
) -> LintResult:
    """
    Lint an OPM deck string.

    Parameters
    ----------
    deck_text     : raw text of the .DATA file
    crash_reports : optional list from runner (OPM stderr already parsed)
    use_llm       : set False to skip LLM stage (faster, offline-safe)

    Returns
    -------
    LintResult with all diagnostics and an optional LLM narrative summary.
    """
    logger.info("Linter: starting static rule engine")

    # Stage 1: static rules
    diagnostics: list[DeckDiagnostic] = []
    for rule in RULES:
        try:
            diagnostics.extend(rule(deck_text))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Rule {rule.__name__} raised: {exc}")

    # Merge crash_reports from the runner (if provided)
    if crash_reports:
        diagnostics.extend(_crash_reports_to_diagnostics(crash_reports))

    logger.info(
        f"Linter: {len(diagnostics)} findings — "
        f"{sum(1 for d in diagnostics if d.severity == DiagnosticSeverity.FATAL)} fatal, "
        f"{sum(1 for d in diagnostics if d.severity == DiagnosticSeverity.ERROR)} error, "
        f"{sum(1 for d in diagnostics if d.severity == DiagnosticSeverity.WARNING)} warning"
    )

    result = LintResult(deck_text=deck_text, diagnostics=diagnostics)

    # Stage 2: LLM narrative (optional)
    if use_llm and _GROQ_API_KEY:
        result.llm_summary = _llm_summarise(deck_text, diagnostics)
    else:
        if use_llm and not _GROQ_API_KEY:
            logger.warning("LLM stage skipped: GROQ_API_KEY not set")
        result.llm_summary = _fallback_summary(diagnostics)

    return result


def lint_file(path: str | Path, **kwargs) -> LintResult:
    """Convenience wrapper — lint a .DATA file on disk."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return lint_deck(text, **kwargs)


# ── LLM stage ─────────────────────────────────────────────────────────────────

def _llm_summarise(
    deck_text: str,
    diagnostics: list[DeckDiagnostic],
) -> str:
    """
    Call Groq LLM to produce a one-paragraph plain-English summary of
    the findings and, for FATAL/ERROR items, generate corrected snippets.
    """
    try:
        from groq import Groq
    except ImportError:
        logger.warning("groq package not installed — LLM stage skipped")
        return _fallback_summary(diagnostics)

    client = Groq(api_key=_GROQ_API_KEY)

    # Build a compact findings JSON for the prompt
    findings_json = json.dumps(
        [
            {
                "rule": d.rule_id,
                "severity": d.severity.value,
                "keyword": d.keyword,
                "message": d.plain_english,
                "fix": d.fix_hint,
            }
            for d in diagnostics
        ],
        indent=2,
    )

    # Truncate deck to first 120 lines for the prompt (keep token count low)
    deck_preview = "\n".join(deck_text.splitlines()[:120])

    prompt = f"""You are an expert OPM reservoir simulation engineer.

I ran a static linter on this OPM deck and found the following issues:

{findings_json}

Here is the beginning of the deck (first 120 lines):

```
{deck_preview}
```

Please write:
1. A single plain-English paragraph (3-5 sentences) summarising what is wrong
   and what the engineer should fix first. Write for a petroleum engineering
   student who understands reservoir concepts but may be new to OPM syntax.
2. For each FATAL or ERROR item, provide a corrected code snippet inside a
   fenced code block labelled with the keyword (e.g. ```WELSPECS).

Do not repeat the rule IDs. Focus on practical guidance."""

    try:
        response = client.chat.completions.create(
            model=_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"LLM call failed: {exc}")
        return _fallback_summary(diagnostics)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _crash_reports_to_diagnostics(reports: list[CrashReport]) -> list[DeckDiagnostic]:
    """Convert runner CrashReports into linter DeckDiagnostics."""
    severity_map = {
        "ERROR":   DiagnosticSeverity.ERROR,
        "WARNING": DiagnosticSeverity.WARNING,
    }
    return [
        DeckDiagnostic(
            severity=severity_map.get(r.severity, DiagnosticSeverity.WARNING),
            keyword=r.keyword or "UNKNOWN",
            raw_message=r.message,
            plain_english=r.message,
            fix_hint="Check the OPM manual for this keyword.",
            line=r.line,
            rule_id="RUNNER",
        )
        for r in reports
    ]


def _fallback_summary(diagnostics: list[DeckDiagnostic]) -> str:
    """Offline summary when LLM is unavailable."""
    if not diagnostics:
        return "No issues found. The deck passes all static checks."
    fatals  = [d for d in diagnostics if d.severity == DiagnosticSeverity.FATAL]
    errors  = [d for d in diagnostics if d.severity == DiagnosticSeverity.ERROR]
    warns   = [d for d in diagnostics if d.severity == DiagnosticSeverity.WARNING]
    parts = []
    if fatals:
        parts.append(f"{len(fatals)} fatal issue(s): " + "; ".join(d.keyword for d in fatals))
    if errors:
        parts.append(f"{len(errors)} error(s): " + "; ".join(d.keyword for d in errors))
    if warns:
        parts.append(f"{len(warns)} warning(s): " + "; ".join(d.keyword for d in warns))
    return "Deck has " + ", ".join(parts) + ". Review each finding above."
