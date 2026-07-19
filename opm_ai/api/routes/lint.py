"""Lint route: POST /api/lint -> linter.lint_deck"""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from opm_ai.api.schemas import LintRequest, LintResult, LintIssue
from opm_ai.linter import lint_deck as lint_deck_func

router = APIRouter()


@router.post("/lint", response_model=LintResult)
async def lint_deck_endpoint(request: LintRequest) -> LintResult:
    """
    Lint an OPM Flow deck file for errors and warnings.

    Delegates to opm_ai.linter.linter.lint_deck.
    """
    try:
        deck_path = Path(request.deck_path)
        result = lint_deck_func(deck_path)

        return LintResult(
            deck_path=result.deck_path,
            issues=[
                LintIssue(
                    severity=issue.severity,
                    section=issue.section,
                    keyword=issue.keyword,
                    line=issue.line,
                    message=issue.message,
                    rule_id=issue.rule_id,
                )
                for issue in result.issues
            ],
            lint_summary=result.lint_summary,
        ).compute_fields() or LintResult(
            deck_path=result.deck_path,
            issues=[
                LintIssue(
                    severity=issue.severity,
                    section=issue.section,
                    keyword=issue.keyword,
                    line=issue.line,
                    message=issue.message,
                    rule_id=issue.rule_id,
                )
                for issue in result.issues
            ],
            lint_summary=result.lint_summary,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))