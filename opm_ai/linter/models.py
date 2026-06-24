# opm_ai/linter/models.py
"""Data contracts for the AI Deck Linter."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DiagnosticSeverity(str, Enum):
    FATAL   = "fatal"    # simulation will not start
    ERROR   = "error"    # simulation starts but results are wrong
    WARNING = "warning"  # suspicious value, may be intentional
    STYLE   = "style"    # best-practice suggestion only


@dataclass
class DeckDiagnostic:
    """
    A single finding from the linter.

    Attributes
    ----------
    severity      : how bad is it
    keyword       : the OPM keyword involved  (e.g. "WELSPECS", "COMPDAT")
    line          : 1-based line number in the deck, if known
    raw_message   : exact text from OPM stderr (or rule description)
    plain_english : what went wrong, in one plain sentence
    fix_hint      : how to fix it, in one plain sentence
    fixed_snippet : corrected keyword block (optional, filled by LLM)
    rule_id       : internal rule identifier (e.g. "R001")
    """
    severity      : DiagnosticSeverity
    keyword       : str
    raw_message   : str
    plain_english : str
    fix_hint      : str
    line          : Optional[int]          = None
    fixed_snippet : Optional[str]          = None
    rule_id       : Optional[str]          = None


@dataclass
class LintResult:
    """Full linting result for one deck."""
    deck_text         : str
    diagnostics       : list[DeckDiagnostic] = field(default_factory=list)
    llm_summary       : str = ""             # one-paragraph LLM narrative
    is_runnable       : bool = True          # False if any FATAL diagnostics

    # ── convenience helpers ──────────────────────────────────────────────
    @property
    def fatals(self)   -> list[DeckDiagnostic]:
        return [d for d in self.diagnostics if d.severity == DiagnosticSeverity.FATAL]

    @property
    def errors(self)   -> list[DeckDiagnostic]:
        return [d for d in self.diagnostics if d.severity == DiagnosticSeverity.ERROR]

    @property
    def warnings(self) -> list[DeckDiagnostic]:
        return [d for d in self.diagnostics if d.severity == DiagnosticSeverity.WARNING]

    @property
    def styles(self)   -> list[DeckDiagnostic]:
        return [d for d in self.diagnostics if d.severity == DiagnosticSeverity.STYLE]

    def __post_init__(self):
        self.is_runnable = len(self.fatals) == 0
