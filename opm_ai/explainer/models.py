"""Data models for the educational explainer module.

This module defines all frozen dataclasses used by the explainer public API
as specified in 07-explainer.md section 3.
"""

from dataclasses import dataclass
from typing import Literal


ExplanationLevel = Literal["beginner", "intermediate", "advanced"]


@dataclass(frozen=True)
class Citation:
    """A single retrievable source citation."""
    source_id: str          # e.g., "dake_ch9", "eclipse_kw_COMPDAT", "spe1_deck_comment_42"
    title: str              # Human-readable title
    url_or_path: str        # File path or URL
    snippet: str            # Relevant excerpt (<= 200 chars)


@dataclass(frozen=True)
class Explanation:
    """Structured explanation returned by explain()."""
    topic: str              # Echo of the input topic/result summary
    level: ExplanationLevel
    text: str               # Markdown-formatted explanation
    citations: tuple[Citation, ...]  # 1-5 citations supporting claims
    follow_up_questions: tuple[str, ...]  # 2-3 suggested follow-ups


@dataclass(frozen=True)
class QuizQuestion:
    """Single multiple-choice question."""
    question: str
    options: tuple[str, str, str, str]  # exactly 4 options A-D
    correct_index: int                  # 0-3
    explanation: str                    # Why the answer is correct (with citation)
    level: ExplanationLevel
    topic_tags: tuple[str, ...]         # e.g., ("waterflood", "watercut", "relative_permeability")


@dataclass(frozen=True)
class Quiz:
    """A set of 3-5 questions on a scenario."""
    scenario_summary: str
    questions: tuple[QuizQuestion, ...]


@dataclass(frozen=True)
class LearningReport:
    """End-of-session summary for student or professor."""
    session_id: str
    topics_covered: tuple[str, ...]
    explanations_generated: int
    questions_asked: int
    quiz_scores: dict[str, float] | None  # if quizzes were taken
    key_concepts: tuple[str, ...]
    citations_used: tuple[Citation, ...]
    markdown: str  # Full report rendered as markdown