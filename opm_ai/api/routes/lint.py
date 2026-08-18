"""Lint route: POST /api/lint -> linter.lint_deck"""

from fastapi import APIRouter, HTTPException

from loguru import logger

from opm_ai.api.paths import validate_deck_path
from opm_ai.api.schemas import LintRequest, LintResult, LintIssue
from opm_ai.linter.linter import lint_deck_combined, lint_deck_v2

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
    """
    try:
        deck_path = validate_deck_path(request.deck_path)
        result = lint_deck_combined(deck_path)

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


from pydantic import BaseModel


class ApplyFixRequest(BaseModel):
    """Request to apply an auto-fix proposal to a deck on disk.

    The proposal parameters (rule_id, line, original_value, new_value)
    are echoed back from the LintIssue.fix_proposal the client saw in
    the /api/lint response. The server re-runs v2 lint to locate the
    matching issue against the current deck text, then applies the
    proposal server-side and returns the patched text + a fresh lint
    result so the UI can replace its state atomically.
    """

    deck_path: str
    rule_id: str
    line: int
    original_value: str
    new_value: str


class ApplyFixResponse(BaseModel):
    deck_text: str
    lint: LintResult


@router.post("/lint/apply-fix", response_model=ApplyFixResponse)
async def apply_fix_endpoint(request: ApplyFixRequest) -> ApplyFixResponse:
    """Apply a single FixProposal server-side and return the new deck.

    The frontend uses this when the user clicks "Apply Fix" on a
    lint issue. We deliberately do NOT accept a pre-computed patched
    text from the client — the server re-runs `propose_fix` so the
    patched text is always authoritative against the current deck
    contents (which the client may have edited since the lint).

    Flow:
      1. Validate deck_path (allowlisted; same contract as /api/lint).
      2. Read deck text from disk.
      3. Run v2 lint to get fresh v2 issues.
      4. Locate the v2 issue matching (rule_id, line).
      5. Call `propose_fix(issue, deck_text)`.
      6. Verify the proposal's original_value/new_value match what
         the client asked for (catches stale UIs).
      7. Write the patched text back to the deck file.
      8. Re-lint and return {deck_text, lint}.
    """
    try:
        deck_path = validate_deck_path(request.deck_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        deck_text = deck_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"cannot read deck: {e}")

    # Re-run v2 to locate the matching issue against current text.
    try:
        v2_result = lint_deck_v2(deck_path)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"v2 lint failed: {type(e).__name__}: {e}",
        )

    # rule_id is "L{code}"; convert to int for matching.
    rule_code_str = request.rule_id.lstrip("L")
    try:
        rule_code = int(rule_code_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"bad rule_id: {request.rule_id}")

    match = None
    for v2i in v2_result.issues:
        if v2i.code == rule_code and v2i.source_line == request.line:
            match = v2i
            break
    if match is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"no {request.rule_id} issue at line {request.line} in the "
                "current deck; reload /api/lint first"
            ),
        )

    # Compute the patched text server-side.
    try:
        from opm_ai.linter.v2.fix_proposals import propose_fix

        proposal = propose_fix(match, deck_text)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"propose_fix raised: {type(e).__name__}: {e}",
        )
    if proposal is None:
        raise HTTPException(
            status_code=422,
            detail=f"{request.rule_id} has no auto-fix for this issue",
        )

    # Verify the client-sent parameters agree with the fresh proposal.
    # Catches stale UIs that clicked Apply on a proposal from an older
    # deck state.
    if (
        proposal.original_value != request.original_value
        or proposal.new_value != request.new_value
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"proposal values drifted: expected "
                f"{request.original_value!r}->{request.new_value!r}, "
                f"got {proposal.original_value!r}->{proposal.new_value!r}; "
                "reload /api/lint first"
            ),
        )

    # Write back and re-lint.
    try:
        deck_path.write_text(proposal.patched_text, encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"cannot write deck: {e}")

    fresh = lint_deck_combined(deck_path)
    return ApplyFixResponse(
        deck_text=proposal.patched_text,
        lint=fresh.model_copy(update={"deck_path": request.deck_path}),
    )
