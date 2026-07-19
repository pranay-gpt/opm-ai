"""Educational Explainer & RAG Engine for Reservoir Simulation.

This module provides AI-powered explanations of reservoir simulation concepts
and results at three pedagogical levels, with citations from a curated
knowledge base. It also generates quizzes and session learning reports.

Key components:
- models.py: Frozen dataclasses (ExplanationLevel, Citation, Explanation, QuizQuestion, Quiz, LearningReport)
- ingest.py: Knowledge base ingestion from Eclipse HTML docs, deck comments, teaching notes
- retrieve.py: Pure-Python BM25 retrieval with level-aware boosting
- explainer.py: Core explain() function with LLM + offline fallback
- quiz.py: Quiz generation (LLM + offline fallback bank)
- report.py: Session learning report generation
"""

from opm_ai.explainer.models import (
    Citation,
    Explanation,
    ExplanationLevel,
    LearningReport,
    Quiz,
    QuizQuestion,
)

__all__ = [
    "Citation",
    "Explanation",
    "ExplanationLevel",
    "LearningReport",
    "Quiz",
    "QuizQuestion",
    # Public API functions (imported from submodules on demand)
    "explain",
    "generate_quiz",
    "generate_learning_report",
    "retrieve_chunks",
    "build_knowledge_base",
]

# Lazy imports for public API to avoid importing heavy deps on import
def __getattr__(name: str):
    if name == "explain":
        from opm_ai.explainer.explainer import explain
        return explain
    if name == "generate_quiz":
        from opm_ai.explainer.quiz import generate_quiz
        return generate_quiz
    if name == "generate_learning_report":
        from opm_ai.explainer.report import generate_learning_report
        return generate_learning_report
    if name == "retrieve_chunks":
        from opm_ai.explainer.retrieve import retrieve_chunks
        return retrieve_chunks
    if name == "build_knowledge_base":
        from opm_ai.explainer.ingest import build_knowledge_base
        return build_knowledge_base
    raise AttributeError(f"module 'opm_ai.explainer' has no attribute '{name}'")