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


def fold_answers(spec: ModelSpec, answers: dict[str, Any]) -> ModelSpec:
    """Apply only the answers already collected, without filling defaults.

    Question applicability is a predicate over the spec: picking
    "gas cap" has to make the GOC question reachable, and asking for a
    fluid has to make the fluid questions reachable. Both are decided from
    the spec, so the answers gathered so far must be folded in BEFORE the
    catalog is folded. Without this the catalog is always evaluated against
    the extraction-only spec, and a blocking rule can name a question the
    user is never offered - a deadlock the interview cannot leave.

    Unlike build_spec this leaves unanswered questions untouched: their
    defaults are not speculative at this point, and applying them would
    make a not-yet-asked question look answered.

    Two passes would not be enough in general, because several answers
    change applicability: the scenario answer gates the GOC and fluid
    questions, and a well's PROD/INJ answer gates its control questions.
    So fold to a fixed point instead - re-derive the applicable set and
    apply anything not yet applied, until a pass adds no new questions.
    Two rounds is the observed maximum; the cap stops a malformed answer
    from spinning.
    """
    applied: set[str] = set()
    for _ in range(4):
        before = len(applied)
        for q in all_questions(spec):
            value = answers.get(q.id)
            if value is not None and q.id not in applied:
                q.apply(spec, value)
                applied.add(q.id)
        if len(applied) == before:
            break
    return spec


def build_spec(spec: ModelSpec, answers: dict[str, Any]) -> ModelSpec:
    """Apply all answered values, then defaults for the rest.

    Two passes, both required. The first folds the answers so the
    catalog's applicability predicates see them - without it a scenario
    answer never makes its gated questions visible, and their defaults
    (the GOC depth, for one) are never recorded, leaving the blocking
    rule that demands them unsatisfiable. The second resolves defaults
    for whatever is still unanswered.
    """
    fold_answers(spec, answers)
    for q in all_questions(spec):
        value = answers.get(q.id)
        if value is not None:
            continue  # already applied by the fold above
        # Absent or None (skipped) -> record the declared default.
        default = q.default
        value = default(spec) if callable(default) else default
        if value is not None:
            q.apply(spec, value)
    return spec
