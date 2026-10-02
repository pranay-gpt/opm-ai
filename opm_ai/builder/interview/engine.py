"""Interview engine: pure functions over (spec, answers).

The client owns the answers dict and round-trips it on every call; the
server is stateless. next_question is a fold over a static catalog, so a
question is reachable only if its predicate holds against the spec built
so far - the "never asks a nonsense question" guarantee by construction.
"""

from typing import Any

from opm_ai.builder.interview.catalog import Question, CATALOG, dynamic_questions
from opm_ai.builder.models import ModelSpec


def all_questions(spec: ModelSpec) -> list[Question]:
    """All questions applicable to the current spec, in catalog order.

    Static catalog entries first, then the per-well dynamic questions.
    """
    return [q for q in CATALOG if q.applies_when(spec)] + dynamic_questions(spec)


def next_question(spec: ModelSpec, answers: dict[str, Any]) -> Question | None:
    """First applicable question not yet answered, or None when complete."""
    for q in all_questions(spec):
        if q.id not in answers:
            return q
    return None


def apply_answer(spec: ModelSpec, question_id: str, value: Any) -> ModelSpec:
    """Write an answered value onto the spec. Unknown ids are ignored -
    the answer set stays authoritative and the interview never breaks on
    a client sending a stale question id."""
    for q in all_questions(spec):
        if q.id == question_id:
            q.apply(spec, value)
            break
    return spec


def progress(spec: ModelSpec, answers: dict[str, Any]) -> dict[str, int]:
    """Answered vs total applicable questions."""
    questions = all_questions(spec)
    return {
        "answered": sum(1 for q in questions if q.id in answers),
        "total": len(questions),
    }


def build_spec(spec: ModelSpec, answers: dict[str, Any]) -> ModelSpec:
    """Apply all answered values, then defaults for the rest.

    Skipped answers record the declared default, so the terminal state
    always builds a deck - the "interview hung" state is not representable.
    """
    for q in all_questions(spec):
        value = answers.get(q.id)
        if value is not None:
            q.apply(spec, value)
        else:
            # Absent or None (skipped) -> record the declared default.
            default = q.default
            value = default(spec) if callable(default) else default
            if value is not None:
                q.apply(spec, value)
    return spec
