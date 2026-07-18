"""Lint models - dataclasses for lint issues and results."""

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class LintIssue:
    """A single lint issue found during deck analysis."""

    severity: Literal["ERROR", "WARNING", "INFO"]
    section: Optional[str]
    keyword: Optional[str]
    line: Optional[int]
    message: str
    rule_id: Optional[str] = None

    def __str__(self) -> str:
        parts = []
        if self.rule_id:
            parts.append(f"[{self.rule_id}]")
        parts.append(f"[{self.severity}]")
        if self.section:
            parts.append(f"Section: {self.section}")
        if self.keyword:
            parts.append(f"Keyword: {self.keyword}")
        if self.line is not None:
            parts.append(f"Line: {self.line}")
        parts.append(self.message)
        return " | ".join(parts)

    def __repr__(self) -> str:
        return f"LintIssue({self.severity}, {self.section}, {self.keyword}, line={self.line}, {self.message!r})"


@dataclass
class LintResult:
    """Result of linting a deck."""

    deck_path: str
    issues: list[LintIssue]
    lint_summary: Optional[str] = None

    @property
    def errors(self) -> list[LintIssue]:
        """All issues with severity ERROR."""
        return [issue for issue in self.issues if issue.severity == "ERROR"]

    @property
    def warnings(self) -> list[LintIssue]:
        """All issues with severity WARNING."""
        return [issue for issue in self.issues if issue.severity == "WARNING"]

    @property
    def info(self) -> list[LintIssue]:
        """All issues with severity INFO."""
        return [issue for issue in self.issues if issue.severity == "INFO"]

    @property
    def passed(self) -> bool:
        """True if no ERROR-level issues."""
        return len(self.errors) == 0

    def __str__(self) -> str:
        if self.passed:
            return f"LintResult({self.deck_path}: Passed, {len(self.warnings)} warnings, {len(self.info)} info)"
        return f"LintResult({self.deck_path}: {len(self.errors)} errors, {len(self.warnings)} warnings, {len(self.info)} info)"