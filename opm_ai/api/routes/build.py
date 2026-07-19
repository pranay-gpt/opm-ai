"""Build route: POST /api/build -> builder.build_deck"""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from opm_ai.api.schemas import BuildRequest, BuildResponse, LintResult, LintIssue
from opm_ai.builder import build_deck

router = APIRouter()


@router.post("/build", response_model=BuildResponse)
async def build_deck_endpoint(request: BuildRequest) -> BuildResponse:
    """
    Build an OPM Flow deck from natural language description.

    Delegates to opm_ai.builder.builder.build_deck.
    """
    try:
        output_path = Path(request.output_path) if request.output_path else None
        deck, lint_result = build_deck(request.description, output_path)

        return BuildResponse(
            deck=deck,
            lint=LintResult(
                deck_path=lint_result.deck_path,
                issues=[
                    LintIssue(
                        severity=issue.severity,
                        section=issue.section,
                        keyword=issue.keyword,
                        line=issue.line,
                        message=issue.message,
                        rule_id=issue.rule_id,
                    )
                    for issue in lint_result.issues
                ],
                lint_summary=lint_result.lint_summary,
            ).compute_fields() or LintResult(
                deck_path=lint_result.deck_path,
                issues=[
                    LintIssue(
                        severity=issue.severity,
                        section=issue.section,
                        keyword=issue.keyword,
                        line=issue.line,
                        message=issue.message,
                        rule_id=issue.rule_id,
                    )
                    for issue in lint_result.issues
                ],
                lint_summary=lint_result.lint_summary,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))