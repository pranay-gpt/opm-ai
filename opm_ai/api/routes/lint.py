"""Lint route: POST /api/lint -> linter.lint_deck"""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from opm_ai.api.paths import validate_deck_path
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
        original_path = request.deck_path
        deck_path = validate_deck_path(original_path)
        result = lint_deck_func(deck_path)

        lint_result = LintResult(
            deck_path=original_path,  # Return original path in response
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
        lint_result.compute_fields()
        return lint_result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))