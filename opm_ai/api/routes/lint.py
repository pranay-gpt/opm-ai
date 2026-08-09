"""Lint route: POST /api/lint -> linter.lint_deck"""

from fastapi import APIRouter, HTTPException

from loguru import logger

from opm_ai.api.paths import validate_deck_path
from opm_ai.api.schemas import LintRequest, LintResult, LintIssue
from opm_ai.linter import lint_deck as lint_deck_func

router = APIRouter()


@router.post("/lint", response_model=LintResult)
async def lint_deck_endpoint(request: LintRequest) -> LintResult:
    """
    Lint an OPM Flow deck file for errors and warnings.

    Delegates to opm_ai.linter.linter.lint_deck. The returned
    LintResult is the canonical Pydantic model from
    opm_ai.linter.models — no dataclass-to-DTO conversion is needed
    because the API schema re-exports the same class.

    Error handling contract (F2.6 audit fix):
    - 400 for ValueError: the deck path or contents are rejected by
      validation before the linter runs (bad path, missing file, etc).
    - 200 with passed=False, errors=[LintIssue(LINT-000, ...)] when the
      linter itself crashes. The frontend then renders the issue in
      the same panel as any other lint error instead of bailing on
      a generic 500. The original trace is logged for diagnosis.
    - 200 with passed=True/False on normal linter output (unchanged).

    Phase 5: each LintIssue carries an `explanation` field with
    Markdown describing what the issue means and how to fix it.
    The frontend renders it in a collapsible "Why this matters?"
    panel. The field is auto-populated by lint_deck; no separate
    round trip to /lint/<id>/explain/<issue_id> is needed.
    """
    try:
        deck_path = validate_deck_path(request.deck_path)
        result = lint_deck_func(deck_path)

        # The linter returns the canonical Pydantic LintResult; only
        # the deck_path is rewritten (to echo the path the client sent,
        # not the validated/canonical one) before responding.
        return result.model_copy(update={"deck_path": request.deck_path})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Linter crashed mid-run (a rule referenced a missing section,
        # a regex blew up on a malformed line, etc). The frontend
        # should still render the deck-status panel; a 500 would just
        # show a generic error toast. Return a structured 200 with a
        # synthetic LINT-000 issue carrying the exception class+message.
        logger.exception("lint_deck crashed for %s", request.deck_path)
        synthetic = LintIssue(
            severity="ERROR",
            section=None,
            keyword=None,
            line=None,
            message=f"Linter crashed: {type(e).__name__}: {e}",
            rule_id="LINT-000",
        )
        return LintResult(
            deck_path=request.deck_path,
            issues=[synthetic],
            lint_summary=None,
        )
