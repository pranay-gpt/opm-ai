"""Phase 3.5: SUMMARY-section FU_* declarations must appear in FUNVAR.

Rule L018 — added by the linter-redesign. FU_* tokens can be defined
two ways in OPM Flow:
  1. Inline via UDQ ASSIGN statements (no FUNVAR needed).
  2. As report variables in SUMMARY section (e.g. FU_MAXWELL).
     These require a FUNVAR declaration so OPM Flow knows the
     variable's units and aggregation method.

This rule fires WARNING when a FU_* token appears in the SUMMARY
section's report-definitions but is NOT declared in FUNVAR. The
deck would error out at runtime; the linter catches it earlier.

Distinguishing "UDQ inline" from "SUMMARY report" is non-trivial:
- UDQ ASSIGN lines live in the SCHEDULE section.
- Summary report definitions live in the SUMMARY section.

Heuristic used here: collect all FU_* tokens from the SUMMARY
section, then check that each appears in some FUNVAR record.
This catches the most common bug ("I added FU_X to my SUMMARY but
forgot the FUNVAR declaration").
"""
import re

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue

FU_TOKEN_RE = re.compile(r"\b(FU_[A-Z][A-Z0-9_]*)\b", re.IGNORECASE)
FUNVAR_HEADER_RE = re.compile(r"(?im)^\s*FUNVAR\b")


def _has_funspec(section_text: str) -> bool:
    """True if the section contains any FUNVAR record."""
    return bool(FUNVAR_HEADER_RE.search(section_text))


def _funvar_tokens(deck: Deck) -> set[str]:
    """Set of FU_* tokens declared across all FUNVAR records.

    FUNVAR records can be back-to-back:
        FUNVAR
          FU_A 1.0 /
          FU_B 1.0 /
        FUNVAR
          FU_C 1.0 /
        /
    So we scan line-by-line: each FUNVAR header starts a record,
    and the record ends at `/` or a non-FUNVAR keyword.

    Distinguishing "data line" from "keyword header" inside a record:
    the spec says data lines start with whitespace (or with a number
    or an FU_/WU_ token). Keyword headers start at column 0 with an
    uppercase letter and have no leading whitespace in the raw line.
    """
    out: set[str] = set()
    runspec_text = deck.get_section("RUNSPEC") or ""
    if not runspec_text:
        return out
    lines = runspec_text.split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if stripped.startswith("FUNVAR"):
            j = i + 1
            while j < len(lines):
                inner_raw = lines[j]
                inner = inner_raw.strip()
                if not inner:
                    j += 1
                    continue
                if inner.startswith("--"):
                    j += 1
                    continue
                if inner == "/" or inner.startswith("/"):
                    break
                # A keyword header has no leading whitespace in the
                # raw line (e.g. "DIMENS" or "FUNVAR"). Data lines
                # start with whitespace, a digit, or a quote.
                if (
                    not inner_raw.startswith((" ", "\t"))
                    and re.match(r"^[A-Z][A-Z0-9_]*\b", inner)
                ):
                    break
                out.update(FU_TOKEN_RE.findall(inner_raw))
                j += 1
            i = j
        else:
            i += 1
    return out


def _summary_fu_tokens(deck: Deck) -> set[str]:
    """Set of FU_* tokens referenced in the SUMMARY section."""
    summary_text = deck.get_section("SUMMARY") or ""
    if not summary_text:
        return set()
    return set(FU_TOKEN_RE.findall(summary_text))


def rule_L019_summary_funvar_missing(deck: Deck) -> list[LintIssue]:
    """L019: SUMMARY references FU_* not declared in FUNVAR (WARNING).

    Phase 3.5 of the linter-redesign. UDQ inline declarations don't
    need FUNVAR; only SUMMARY report definitions do. This rule
    bridges the gap.

    Rule id L019 chosen because L018 is already taken by
    `schedule.rule_L018_injector_no_wconinje`.
    """
    funvar_tokens = _funvar_tokens(deck)
    summary_fu = _summary_fu_tokens(deck)
    missing = {tok.upper() for tok in summary_fu} - {
        tok.upper() for tok in funvar_tokens
    }
    if not missing:
        return []
    return [LintIssue(
        severity="WARNING",
        section="SUMMARY",
        keyword="FUNVAR",
        line=None,
        message=(
            f"SUMMARY references FU_* tokens not declared in FUNVAR: "
            f"{sorted(missing)}. Add a FUNVAR record for each."
        ),
        rule_id="L019",
    )]