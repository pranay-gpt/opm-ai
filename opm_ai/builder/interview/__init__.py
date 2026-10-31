"""Reservoir-context interview: section-by-step questioning for the builder.

Pure functions over (spec, answers). The client owns the answers dict;
the server is stateless. See IMPLEMENTATION_PLAN.md Stage 3.
"""

from opm_ai.builder.interview.catalog import Question, CATALOG, dynamic_questions
from opm_ai.builder.interview.engine import (
    next_question,
    apply_answer,
    build_spec,
    fold_answers,
    progress,
    all_questions,
)
from opm_ai.builder.interview.rules import Finding, validate

__all__ = [
    "Question",
    "CATALOG",
    "dynamic_questions",
    "next_question",
    "apply_answer",
    "build_spec",
    "fold_answers",
    "progress",
    "all_questions",
    "Finding",
    "validate",
]
