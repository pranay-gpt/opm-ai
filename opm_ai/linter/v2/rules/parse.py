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

Each `Deck.parse_errors` entry is a string of the form
`<location>: <message>`. We split on the first `: ` to recover the
file/line location and pass the rest as the message.
"""

from __future__ import annotations

from pathlib import Path

from ..ast import Deck
from ..symbols import SymbolTable
from ..validator import LintIssue, Severity, register


def _split_location(entry: str) -> tuple[Path | None, int | None, str]:
    """Parse `file:line: message` or `file: message` or `message`.

    Returns (file, line, message). file/line may be None if the
    entry doesn't carry a location prefix.
    """
    # Entries are formatted as "<location>: <message>" where location
    # is either "file:line" or just "file". The message itself may
    # legitimately contain ": " (e.g. "valid sections: ['SUMMARY']"),
    # so we split only the first occurrence.
    if ":" not in entry:
        return None, None, entry
    head, _, msg = entry.partition(": ")
    # head may now be "file:line" — split on the last ":" in head.
    if ":" in head:
        # file:line where file may contain ":" on Windows; we
        # use rsplit with maxsplit=1 to peel off the trailing ":line".
        fname, _, lineno = head.rpartition(":")
        try:
            return Path(fname), int(lineno), msg
        except ValueError:
            # The trailing component wasn't an int — treat the
            # whole head as the file and the message includes the rest.
            return Path(head), None, msg
    return Path(head), None, msg


def parse_error_rule(deck: Deck, symbol_table: SymbolTable) -> list[LintIssue]:
    """Surface `Deck.parse_errors` as LintIssues (L160, INFO)."""
    issues: list[LintIssue] = []
    for entry in deck.parse_errors:
        src, line, msg = _split_location(entry)
        issues.append(
            LintIssue(
                code=160,
                severity=Severity.INFO,
                message=msg,
                source_file=src,
                source_line=line,
            )
        )
    return issues


def register() -> None:
    """Register this rule with the validator."""
    from ..validator import register as _register
    _register(160, 169, "parse", parse_error_rule)


register()
