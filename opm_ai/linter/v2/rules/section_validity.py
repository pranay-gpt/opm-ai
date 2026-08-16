"""L170-L179: section validity checks.

Catches:
- L170: keyword used in a section that's not in its catalogue section
  list (INFO). Parser already records this via `kw.unknown_reason`
  but no rule consumed it.
- L171: unknown keyword (INFO). Same pattern; the message starts
  with "unknown keyword" rather than the section-mismatch form.

Both severities are INFO. Rationale:
- L170 is INFO because the parser is overly eager: it sets
  unknown_reason on any keyword that appears in a section not
  listed in its catalogue spec, but Eclipse/OPM Flow are
  tolerant of misplaced keywords (e.g. WCONPROD after RUNSPEC
  with no explicit SCHEDULE header in fixture SPE5). WARNING
  would push these into the corpus gate's 5-warning-per-fixture
  budget for fixtures that OPM Flow accepts as-is.
- L171 is INFO because the v2 catalogue is intentionally a
  strict subset of the full OPM-Flow-supported keyword set.
  Many real OPM keywords (WGOR, FGOR, BPR, COORDSYS, RPTSOL,
  BOX, ENDBOX, COMPLUMP, WECON, WTEST, UDQDIMS, EQLOPTS, etc.)
  are not yet catalogued. Surfacing each as WARNING would flood
  the corpus gate with thousands of false positives. INFO puts
  L171 on par with L160 (parse-time loose tokens), which has
  the same "diagnostic only" character.

PRELUDE (a virtual section for keywords that appear before any
section header, typically in INCLUDEd fragment files) is skipped:
those keywords are valid, the parser just didn't have a real
section to attach them to. The resolver merges them into the
INCLUDE-statement's parent section.

SUMMARY section keywords with unknown_reason are also suppressed:
SUMMARY is a free-form section where bare column-0 tokens are
SUMMARY variable declarations (FOPR, WOPR:W1, ROIP, WGOR, FGOR,
BPR, RPR, etc.) rather than catalogued keywords. The symbol table
already harvests them into `summary_vars`; L171 firing there would
produce thousands of false positives on every fixture. SUMMARY
mnemonics are catalogued as `summary_vars` not as keyword specs.

We also re-check the keyword's current section against its spec.
The parser sets `unknown_reason` based on the section at parse
time, but the resolver may have moved the keyword to a different
section afterwards (a PRELUDE keyword merged into its parent's
SCHEDULE section, for example). The text of the L170 reason still
says "PRELUDE" but the keyword is now in a valid section; in that
case the issue is a resolver artifact, not a real defect, so we
suppress the L170.
"""

from __future__ import annotations

from pathlib import Path

from ..ast import Deck
from ..spec import SectionName
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


def section_validity_rule(deck: Deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Walk every keyword with unknown_reason set, emit L170 or L171."""
    issues: list[LintIssue] = []
    for section in deck.sections.values():
        if section.name == SectionName.PRELUDE:
            continue
        for kw in section.keywords:
            if not kw.unknown_reason:
                continue
            if not kw.header_token:
                continue
            # PRELUDE (a virtual section for keywords that arrived
            # before any section header, typically from an INCLUDEd
            # fragment) is a parser artifact, not a real OPM section.
            if (
                kw.section is not None
                and kw.section.name == SectionName.PRELUDE
            ):
                continue
            # SUMMARY section keywords are bare variable declarations
            # (FOPR, WOPR:W1, WGOR, FGOR, BPR, RPR, ROIP, etc.), not
            # catalogued keywords. The symbol table already harvests
            # them into summary_vars. Suppress L171 here to avoid
            # thousands of false positives on every fixture that uses
            # the SUMMARY section.
            if section.name == SectionName.SUMMARY:
                continue
            # L170 vs L171: a section-mismatch reason text is L170,
            # but only when the mismatch is still real at lint time.
            # If the resolver has since moved the keyword to a valid
            # section, the parse-time reason is stale — suppress.
            reason = kw.unknown_reason
            if not reason.startswith("unknown keyword"):
                # Section-mismatch path. Decide L170 vs suppress.
                if (
                    kw.spec is not None
                    and kw.section is not None
                    and kw.spec.is_valid_in(kw.section.name)
                ):
                    # Resolver moved the keyword; the parse-time
                    # mismatch is no longer current.
                    continue
            src = (
                Path(kw.header_token.source_file)
                if kw.header_token.source_file
                else None
            )
            line = kw.header_token.line
            if reason.startswith("unknown keyword"):
                issues.append(
                    LintIssue(
                        code=171,
                        severity=Severity.INFO,
                        message=reason,
                        source_file=src,
                        source_line=line,
                        keyword=kw,
                    )
                )
            else:
                # Section-mismatch form (L170). INFO (not WARNING)
                # because the parser is overly eager: it sets
                # unknown_reason on any keyword that appears in a
                # section not listed in its catalogue spec, but
                # Eclipse/OPM Flow are tolerant of misplaced
                # keywords (e.g. WCONPROD after RUNSPEC with no
                # explicit SCHEDULE header in fixture SPE5). WARNING
                # would push these into the corpus gate's
                # 5-warning-per-fixture budget for fixtures that
                # OPM Flow accepts as-is. Promote L170 to WARNING
                # only after the parser handles section inheritance
                # from preceding sections and INCLUDE-context.
                issues.append(
                    LintIssue(
                        code=170,
                        severity=Severity.INFO,
                        message=reason,
                        source_file=src,
                        source_line=line,
                        keyword=kw,
                    )
                )
    return issues


def register() -> None:
    """Register this rule with the validator."""
    from ..validator import register as _register
    _register(170, 179, "section_validity", section_validity_rule)


register()
