"""L016: Unknown keyword (WARNING).

A keyword in the deck that does not appear in the union of the two
catalogues is flagged as a hint. Severity is WARNING: the deck still
passes lint, the builder still ships it. The "did you mean?" suggestion
uses difflib.get_close_matches with cutoff=0.6 (Python default).

Sources:
1. `opm_ai/linter/keywords.json` — observational, built by
   `scripts/build_keyword_catalogue.py` from `tests/fixtures/`. Records
   every keyword observed across 730 fixture decks with per-section
   counts and an example first record.
2. `opm_ai/linter/keywords_rm.json` — authoritative, built by
   `scripts/build_keyword_rm_catalogue.py` from
   `tests/eclipse/ecl_rm/*.html` (Eclipse Reference Manual, MIT-
   compatible CC-BY-4.0). Records the canonical section placement
   (flagtable), parameter item count, and a short description per
   keyword (~1942 keywords).

The L016 rule unions both. Calibration against the fixture catalogue
remains 0 false positives (the union can only add recognition, not
remove it). When a fixture-only keyword matches an ERM-only keyword,
the fixture record wins (richer observational data).

Honest limitation: a valid ECLIPSE keyword neither the manual nor any
fixture documents is flagged. To extend coverage, regenerate either
catalogue: add fixtures, run `scripts/build_keyword_catalogue.py`;
update the manual source, run `scripts/build_keyword_rm_catalogue.py`.

Phase 1 (linter-redesign branch): user-defined UDQ variables
(`FU_*`, `WU_*`) are recognised by `Deck._classify_token` as
`TokenType.USER_VARIABLE` and skipped here. They are NOT in the
catalogue and never produce L016 issues. The catalogue scrape
also filters them out so the catalogue size is bounded by real
keywords, not by user-variable vocabulary.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Optional

from opm_ai.linter.deck import Deck, TokenType
from opm_ai.linter.models import LintIssue

# Same regex the L001 rule uses for per-line keyword detection. Tokenising
# the same way the rest of the linter does prevents the catalogue and the
# rule from disagreeing on what counts as a keyword.
_KEYWORD_LINE_RE = re.compile(
    r"^([A-Z][A-Z0-9_]*)\s*(?:--.*)?$",
    re.IGNORECASE,
)

# Tokens that look like keywords but aren't. The Deck class treats these as
# section boundaries, not payloads.
_SECTION_HEADERS = frozenset({
    "RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS",
    "SOLUTION", "SUMMARY", "SCHEDULE", "ENDFIN",
})

# Other tokens to ignore: '/' alone, END on its own.
_SKIP_TOKENS = frozenset({"END"})

# Suggested-match cutoff. 0.6 is the Python default; calibrated to catch
# transposed letters (WELSPEC -> WELSPECS, ratio ~0.875) while rejecting
# random typos (XYZABC, ratio to WELSPECS ~0.14).
_SUGGEST_CUTOFF = 0.6

# Lazy catalogue cache. Loading once per process keeps the per-rule-call
# cost to a dict lookup.
_CATALOGUE: Optional[dict[str, dict]] = None
_CATALOGUE_PATH = Path(__file__).parent.parent / "keywords.json"
_RM_CATALOGUE_PATH = Path(__file__).parent.parent / "keywords_rm.json"


def _get_catalogue() -> dict[str, dict]:
    """Lazy-load the keyword catalogue from the JSON artefacts.

    Returns the inner `keywords` dict (keyword -> record). Two sources are
    unioned at first load:

    1. `keywords.json` (the fixture-derived observational catalogue; 1079
       keywords across 730 fixture decks). This is the calibrated source:
       the L016 rule was tuned against it for zero false positives.
    2. `keywords_rm.json` (the Eclipse Reference Manual-derived
       authoritative catalogue; ~1942 keywords across the manual). The
       union means the linter recognises keywords that no fixture uses
       (advanced compositional, thermal, polymer, etc.) without losing
       the calibration. Strictness only ever increases: a keyword
       present in either source is accepted.

    Returns an empty dict if neither file exists; the rule then fires on
    every keyword (loud but harmless — the deck still passes lint).
    """
    global _CATALOGUE
    if _CATALOGUE is not None:
        return _CATALOGUE
    merged: dict[str, dict] = {}
    if _CATALOGUE_PATH.exists():
        with _CATALOGUE_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        merged.update(data.get("keywords", {}))
    if _RM_CATALOGUE_PATH.exists():
        with _RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        for name, record in data.get("keywords", {}).items():
            if name not in merged:
                merged[name] = record
            # If both sources have it, keep the fixture record (which has
            # richer observational data: deck_count, record_count, etc.).
    _CATALOGUE = merged
    return _CATALOGUE


def _suggest(token: str, catalogue: dict[str, dict]) -> Optional[str]:
    """Return the closest catalogue key to `token`, or None.

    Case-insensitive (the token is uppercased before lookup). Looks at all
    catalogue keys; the catalogue is small enough (~1k entries) that this
    is fine.
    """
    if not catalogue:
        return None
    matches = difflib.get_close_matches(
        token.upper(), catalogue.keys(), n=1, cutoff=_SUGGEST_CUTOFF
    )
    return matches[0] if matches else None


def rule_L016_unknown_keyword(deck: Deck) -> list[LintIssue]:
    """L016: Unknown keyword (WARNING).

    For each keyword-line token that is not in the catalogue, emit a
    LintIssue with WARNING severity. The message includes a "did you mean
    X?" suggestion if difflib finds a close match.
    """
    issues: list[LintIssue] = []
    catalogue = _get_catalogue()
    if not catalogue:
        # No catalogue available; the rule cannot flag anything. This is a
        # build pipeline issue, not a runtime condition.
        return issues

    for section_name in deck.sections:
        # SUMMARY is exempt: its mnemonics (FGPR, ALL, RUNSUM, ...) are bare
        # flags or self-terminating and the catalogue is incomplete on them.
        if section_name.upper() == "SUMMARY":
            continue

        section_text = deck.get_section(section_name)
        if not section_text:
            continue

        section_lines = section_text.split("\n")
        section_start_line: Optional[int] = None
        section_line_range = deck.get_section_lines(section_name)
        if section_line_range is not None:
            section_start_line = section_line_range[0]

        for i, line in enumerate(section_lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            match = _KEYWORD_LINE_RE.match(stripped)
            if not match:
                continue
            token_upper = match.group(1).upper()
            if token_upper in _SECTION_HEADERS or token_upper in _SKIP_TOKENS:
                continue
            # Phase 1: user-defined variables (FU_*, WU_*) are valid by
            # definition; skip them rather than consulting the catalogue.
            # This stops L016 from firing on arbitrary UDQ mnemonics the
            # user defines at runtime (see docs/personal/LINTER_REDESIGN_PLAN.md).
            if Deck._classify_token(token_upper) is TokenType.USER_VARIABLE:
                continue
            if token_upper in catalogue:
                continue

            suggestion = _suggest(token_upper, catalogue)
            if suggestion:
                message = (
                    f"Unknown keyword '{match.group(1)}' in {section_name}; "
                    f"did you mean '{suggestion}'?"
                )
            else:
                message = (
                    f"Unknown keyword '{match.group(1)}' in {section_name}"
                )

            actual_line = None
            if section_start_line is not None:
                actual_line = section_start_line + i - 1

            issues.append(LintIssue(
                severity="WARNING",
                section=section_name,
                keyword=match.group(1),
                line=actual_line,
                message=message,
                rule_id="L016",
            ))

    return issues
