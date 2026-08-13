"""LintIssue model and validator framework for v2.

The validator walks a CompositeDeck, runs a registry of rules, and
collects LintIssues. Each issue has a code (L200, L210, etc.),
severity (ERROR, WARNING, INFO), source location, and message.

The rule registry lets each rule family (shape, range, crossref,
dims, requires, udq, section, opm) register its checks independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .ast import Deck, Keyword
from .symbols import SymbolTable


class Severity(str, Enum):
    """Lint issue severity."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class LintIssue:
    """A single lint issue.

    Attributes:
        code: Rule code (L200, L210, ..., L279).
        severity: ERROR / WARNING / INFO.
        message: Human-readable description.
        source_file: File where the issue was detected (None for
            deck-wide rules).
        source_line: Line number (None for deck-wide rules).
        keyword: The keyword that triggered the issue (if any).
    """

    code: int
    severity: Severity
    message: str
    source_file: Optional[Path] = None
    source_line: Optional[int] = None
    keyword: Optional[Keyword] = None

    def location_str(self) -> str:
        """Human-readable location: `file:line` or `file` or empty."""
        if self.source_file is not None and self.source_line is not None:
            return f"{self.source_file.name}:{self.source_line}"
        if self.source_file is not None:
            return f"{self.source_file.name}"
        return ""


@dataclass
class LintResult:
    """Result of running all rules against a deck.

    Attributes:
        issues: All issues collected (in rule-discovery order).
        symbol_table: The symbol table used for cross-references.
        deck: The deck that was linted.
    """

    issues: list[LintIssue] = field(default_factory=list)
    symbol_table: Optional[SymbolTable] = None
    deck: Optional[Deck] = None

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.INFO)

    def has_errors(self) -> bool:
        return self.error_count() > 0

    def filter(self, code: int) -> list[LintIssue]:
        return [i for i in self.issues if i.code == code]


# A rule is a function that takes (deck, symbol_table) and yields
# LintIssues. Rules are pure (no mutation of inputs).
Rule = Callable[[Deck, SymbolTable], list[LintIssue]]


# Rule registry: list of (code_prefix, name, rule_fn) tuples.
# Rules are run in order; the first matching prefix wins for filtering.
_RULES: list[tuple[int, int, str, Rule]] = []


def register(code_lo: int, code_hi: int, name: str, rule: Rule) -> None:
    """Register a rule in the global registry."""
    _RULES.append((code_lo, code_hi, name, rule))


def clear_rules() -> None:
    """Drop all registered rules. Tests use this for isolation."""
    _RULES.clear()


def list_rules() -> list[tuple[int, int, str]]:
    """List all registered rules (code range, name)."""
    return [(lo, hi, name) for lo, hi, name, _ in _RULES]


# Auto-import the rule modules so they register themselves.
# (Defer the import to avoid circular dependencies at module load.)
def _register_builtin_rules() -> None:
    from .rules import crossref, dims, opm, parse, requires, section, shape  # noqa: F401


_register_builtin_rules()


def reset_rules() -> None:
    """Drop and re-register all built-in rules.

    Tests use this for isolation after calling clear_rules().
    Idempotent — re-registering a rule that already exists replaces
    its entry rather than duplicating.

    Note: we explicitly invoke each module's register() function
    rather than relying on import side effects, because Python
    caches modules and won't re-execute `register()` calls on a
    second import.
    """
    clear_rules()
    from .rules import crossref, dims, opm, parse, requires, section, shape
    crossref.register()
    dims.register()
    opm.register()
    parse.register()
    requires.register()
    section.register()
    shape.register()


def validate(deck: Deck, symbol_table: Optional[SymbolTable] = None) -> LintResult:
    """Run all registered rules against a deck.

    Args:
        deck: The deck (or CompositeDeck.main_deck) to lint.
        symbol_table: Optional pre-built symbol table. If None, builds
            one via `build_symbol_table`.

    Returns:
        LintResult with all collected issues.
    """
    if symbol_table is None:
        from .symbols import build_symbol_table
        symbol_table = build_symbol_table(deck)

    result = LintResult(symbol_table=symbol_table, deck=deck)
    for lo, hi, name, rule in _RULES:
        try:
            issues = rule(deck, symbol_table)
            result.issues.extend(issues)
        except Exception as e:  # pragma: no cover - rule crashes should be visible
            result.issues.append(
                LintIssue(
                    code=lo,
                    severity=Severity.ERROR,
                    message=f"rule {name!r} crashed: {type(e).__name__}: {e}",
                )
            )
    return result