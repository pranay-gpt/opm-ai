"""Lint models - Pydantic models for lint issues and results.

The same models are used in-process (by the linter, rules, builder) and
on the wire (the API re-exports them as request/response DTOs). Keeping
a single canonical shape eliminates the dataclass-to-Pydantic conversion
boilerplate that used to live in two routes.

`LintResult.errors` (a list of error *messages*) and `.passed` are
auto-derived from `.issues` via a model_validator, so callers can build
a LintResult with just the issues and the wire-format fields appear
without a separate compute_fields() pass.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LintIssue(BaseModel):
    """A single lint issue found during deck analysis."""

    model_config = ConfigDict(from_attributes=True)

    severity: Literal["ERROR", "WARNING", "INFO"]
    section: Optional[str] = None
    keyword: Optional[str] = None
    line: Optional[int] = None
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
        return (
            f"LintIssue({self.severity}, {self.section}, {self.keyword}, "
            f"line={self.line}, {self.message!r})"
        )


class LintResult(BaseModel):
    """Result of linting a deck.

    The dataclass version of this class exposed `.errors` and
    `.warnings` as lists of LintIssue. The Pydantic wire format used by
    the API exposes `.errors` as a list of error messages (str) plus a
    `.passed` boolean, so the frontend can render the verdict without
    iterating. Both shapes are preserved here:

    - `.issues` and `.error_issues` / `.warning_issues` give the rich
      LintIssue lists.
    - `.errors` and `.passed` give the wire-format summary and are
      auto-derived by a validator from `.issues`, so callers do not
      have to call a separate compute_fields() pass.
    """

    model_config = ConfigDict(from_attributes=True)

    deck_path: str
    issues: list[LintIssue] = Field(default_factory=list)
    lint_summary: Optional[str] = None
    # Wire-format derived fields. Populated automatically by the
    # validator below; defaults exist so a LintResult(issues=[]) is
    # well-formed.
    errors: list[str] = Field(default_factory=list)
    passed: bool = True

    @model_validator(mode="after")
    def _compute_summary(self) -> "LintResult":
        self.errors = [i.message for i in self.issues if i.severity == "ERROR"]
        self.passed = len(self.errors) == 0
        return self

    @property
    def error_issues(self) -> list[LintIssue]:
        """The issues themselves (not the messages) whose severity is
        ERROR. Use this when the consumer needs the rule_id / line /
        section — `.errors` is just the human-readable messages."""
        return [i for i in self.issues if i.severity == "ERROR"]

    @property
    def warning_issues(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "WARNING"]

    @property
    def info(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "INFO"]

    @property
    def warnings(self) -> list[LintIssue]:
        """Backwards-compatible alias for the dataclass property name
        that some callers (and the chat tool code) still use."""
        return self.warning_issues

    def __str__(self) -> str:
        if self.passed:
            return (
                f"LintResult({self.deck_path}: Passed, "
                f"{len(self.warnings)} warnings, {len(self.info)} info)"
            )
        return (
            f"LintResult({self.deck_path}: {len(self.errors)} errors, "
            f"{len(self.warnings)} warnings, {len(self.info)} info)"
        )
