"""Interview route: POST /api/interview/next and /api/interview/finish.

The server is stateless: the client owns the answers dict and round-trips
it on every call. next_question is a fold over a static catalog, so a
question is reachable only when its predicate holds against the spec built
so far - the "never asks a nonsense question" guarantee by construction.

finish() is the terminal state: it refuses to return while a blocking
question is unanswered, and the spec it returned always builds a
lint-passing deck (skipped answers record the declared default).
"""

from fastapi import APIRouter, HTTPException

from opm_ai.api.schemas import (
    FinishRequest,
    FinishResponse,
    InterviewRequest,
    InterviewResponse,
    ProgressDTO,
    QuestionDTO,
)
from opm_ai.builder.models import ScenarioType
from opm_ai.builder import extract_parameters_offline
from opm_ai.builder.builder import build_deck_from_spec
from opm_ai.builder.interview import all_questions, build_spec, next_question, validate
from opm_ai.builder.interview.ingest import apply_ingest, parse_paste

router = APIRouter()

# Special answer key the client uses to hand a pasted/uploaded file to the
# interview. It is stripped before the answers dict reaches the engine,
# which knows nothing about ingestion - the two features compose.
_INGEST_KEY = "__ingest"


def _spec_for(request: InterviewRequest):
    """Extract the spec from the description, applying any ingested paste."""
    spec = extract_parameters_offline(request.description)
    ingest_text = request.answers.get(_INGEST_KEY)
    if ingest_text:
        apply_ingest(spec, parse_paste(ingest_text))
    return spec


def _answers(request: InterviewRequest) -> dict:
    return {k: v for k, v in request.answers.items() if k != _INGEST_KEY}


def _question_dto(q, spec) -> QuestionDTO:
    # The catalog's `default` is a value or a callable over the spec; the
    # UI needs the resolved value, so evaluate it here. Callables that
    # return None (e.g. "blank = none") stay null on the wire.
    raw = q.default
    value = raw(spec) if callable(raw) else raw
    if isinstance(value, ScenarioType):
        value = value.value
    return QuestionDTO(
        id=q.id,
        section=q.section,
        prompt=q.prompt,
        kind=q.kind,
        default=value,
        units=q.units,
        options=q.options,
        blocking=q.blocking,
    )


def _resolved(spec) -> dict:
    """The rock-basics snapshot the UI renders, same shape as /api/build."""
    from opm_ai.api.schemas import ROCK_BASICS_FIELDS

    out: dict = {}
    for field in ROCK_BASICS_FIELDS:
        v = getattr(spec.reservoir, field)
        out[field] = list(v) if isinstance(v, list) else v
    return out


@router.post("/interview/next", response_model=InterviewResponse)
async def interview_next(request: InterviewRequest) -> InterviewResponse:
    """Return the next question to ask, or null when the interview is done.

    The client sends the answers it has collected so far; the server folds
    the catalog against the spec built so far and returns the first
    applicable question that has not been answered. Unknown answer ids are
    ignored (a stale client cannot break the interview).
    """
    try:
        spec = _spec_for(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"could not build spec: {e}")

    answers = _answers(request)
    questions = all_questions(spec)
    q = next_question(spec, answers)
    return InterviewResponse(
        question=_question_dto(q, spec) if q else None,
        progress=ProgressDTO(
            answered=sum(1 for qq in questions if qq.id in answers),
            total=len(questions),
        ),
        resolved=_resolved(spec),
    )


@router.post("/interview/finish", response_model=FinishResponse)
async def interview_finish(request: InterviewRequest) -> FinishResponse:
    """Terminal state: build the deck from every answered value.

    Blocking questions must be answered; a skipped answer still records
    the declared default, so the returned spec always builds a
    lint-passing deck - the "interview hung" state is not representable.
    """
    try:
        spec = _spec_for(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"could not build spec: {e}")

    answers = _answers(request)

    # Apply answers first, then validate the built spec. A skipped blocking
    # question records its declared default, so validate passes - blocking
    # only stops a bare finish where the user actively left something wrong.
    built = build_spec(spec, answers)
    findings = validate(built, answers)
    blocking = [f for f in findings if f.severity == "block"]
    if blocking:
        raise HTTPException(
            status_code=422,
            detail="blocking questions unanswered: "
            + "; ".join(f.message for f in blocking),
        )

    deck, lint = build_deck_from_spec(built)
    return FinishResponse(
        deck=deck,
        lint=lint,
        resolved=_resolved(built),
        findings=[f.message for f in findings if f.severity == "warn"],
    )