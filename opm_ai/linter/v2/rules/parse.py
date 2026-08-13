"""L160-L169: parse-level errors surfaced as LintIssues.

The parser accumulates structural errors in `Deck.parse_errors`
(loose tokens before any keyword, unknown section headers, sections
out of canonical order, etc.). Without this rule those errors are
silently dropped — the linter would report clean on a deck that
the parser couldn't actually structure.

Severity is INFO by default because most of these entries are
diagnostic (e.g. value tokens emitted from comment-line decoration
before the first section header), not actionable deck defects.
Users running with `--strict` can promote INFO to WARNING.

Each `Deck.parse_errors` entry is a `ParseError` dataclass
(`source_file`, `line`, `col`, `message`). We use it directly to
construct `LintIssue`s — no string parsing needed.
"""

from __future__ import annotations

from ..ast import Deck, ParseError
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


def parse_error_rule(deck: Deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Surface `Deck.parse_errors` as LintIssues (L160, INFO)."""
    issues: list[LintIssue] = []
    for entry in deck.parse_errors:
        # entry is a ParseError — extract location/message directly.
        if isinstance(entry, ParseError):
            src, line, msg = entry.source_file, entry.line, entry.message
            severity = entry.severity_hint or Severity.INFO
        else:
            # Backward compatibility: legacy string-format entries.
            src, line, msg = _split_legacy_location(entry)
            severity = Severity.INFO
        issues.append(
            LintIssue(
                code=160,
                severity=severity,
                message=msg,
                source_file=src,
                source_line=line,
            )
        )
    return issues


def _split_legacy_location(entry: str) -> tuple:
    """Backward-compat shim for old `line:col: msg` string entries.

    Returns (source_file=None, line=int|None, message=str).
    """
    if ":" not in entry:
        return None, None, entry
    head, _, msg = entry.partition(": ")
    if ":" in head:
        _, _, lineno = head.rpartition(":")
        try:
            return None, int(lineno), msg
        except ValueError:
            return None, None, msg
    return None, None, msg


def register() -> None:
    """Register this rule with the validator."""
    from ..validator import register as _register
    _register(160, 169, "parse", parse_error_rule)


register()
