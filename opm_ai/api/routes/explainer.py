"""Explainer routes: POST /api/explain, /api/quiz, /api/learning-report"""

import asyncio
from fastapi import APIRouter, HTTPException

from opm_ai.api.schemas import (
    ExplainRequest,
    ExplainResponse,
    QuizRequest,
    QuizResponse,
    LearningReportRequest,
    LearningReportResponse,
)
from opm_ai.explainer import explain, generate_quiz, generate_learning_report
from opm_ai.explainer.models import ExplanationLevel

router = APIRouter()


def _explanation_to_response(exp) -> ExplainResponse:
    """Convert Explanation dataclass to ExplainResponse."""
    # Convert frozen dataclass to dict - tuples become lists via json round-trip
    citations = []
    for c in exp.citations:
        citations.append({
            "source_id": c.source_id,
            "title": c.title,
            "url_or_path": c.url_or_path,
            "snippet": c.snippet,
        })

    return ExplainResponse(
        topic=exp.topic,
        level=exp.level,
        text=exp.text,
        citations=citations,
        follow_up_questions=list(exp.follow_up_questions),
    )


def _quiz_to_response(quiz) -> QuizResponse:
    """Convert Quiz dataclass to QuizResponse."""
    questions = []
    for q in quiz.questions:
        questions.append({
            "question": q.question,
            "options": list(q.options),
            "correct_index": q.correct_index,
            "explanation": q.explanation,
            "level": q.level,
            "topic_tags": list(q.topic_tags),
        })

    return QuizResponse(
        scenario_summary=quiz.scenario_summary,
        questions=questions,
    )


def _report_to_response(report) -> LearningReportResponse:
    """Convert LearningReport dataclass to LearningReportResponse."""
    citations = []
    for c in report.citations_used:
        citations.append({
            "source_id": c.source_id,
            "title": c.title,
            "url_or_path": c.url_or_path,
            "snippet": c.snippet,
        })

    return LearningReportResponse(
        session_id=report.session_id,
        topics_covered=list(report.topics_covered),
        explanations_generated=report.explanations_generated,
        questions_asked=report.questions_asked,
        quiz_scores=report.quiz_scores,
        key_concepts=list(report.key_concepts),
        citations_used=citations,
        markdown=report.markdown,
    )


@router.post("/explain", response_model=ExplainResponse)
async def explain_endpoint(request: ExplainRequest) -> ExplainResponse:
    """
    Generate an explanation for a topic or KPI summary.

    Body: {topic: str | null, kpis: dict | null, level: "beginner"|"intermediate"|"advanced", context: dict | null}
    Exactly one of topic or kpis is required.
    """
    # Validate exactly one of topic or kpis
    has_topic = request.topic is not None and request.topic.strip() != ""
    has_kpis = request.kpis is not None and len(request.kpis) > 0

    if not has_topic and not has_kpis:
        raise HTTPException(
            status_code=422,
            detail="Exactly one of 'topic' or 'kpis' is required"
        )
    if has_topic and has_kpis:
        raise HTTPException(
            status_code=422,
            detail="Provide either 'topic' or 'kpis', not both"
        )

    topic_or_kpis = request.topic if has_topic else request.kpis

    # Run in executor to avoid blocking event loop (LLM or KB build can take 500ms-2s)
    loop = asyncio.get_event_loop()
    explanation = await loop.run_in_executor(
        None,
        lambda: explain(topic_or_kpis, level=request.level, context=request.context)
    )

    return _explanation_to_response(explanation)


@router.post("/quiz", response_model=QuizResponse)
async def quiz_endpoint(request: QuizRequest) -> QuizResponse:
    """
    Generate a multiple-choice quiz from a scenario summary.

    Body: {scenario_summary: str, level: str = "intermediate", n_questions: int = 3, topic_focus: list[str] | null}
    """
    loop = asyncio.get_event_loop()
    quiz = await loop.run_in_executor(
        None,
        lambda: generate_quiz(
            request.scenario_summary,
            level=request.level,
            n_questions=request.n_questions,
            topic_focus=request.topic_focus,
        )
    )

    return _quiz_to_response(quiz)


@router.post("/learning-report", response_model=LearningReportResponse)
async def learning_report_endpoint(request: LearningReportRequest) -> LearningReportResponse:
    """
    Generate a learning report from a conversation session.

    Body: {session_id: str, conversation_history: list[dict], kpis_history: list[dict] | null}
    """
    loop = asyncio.get_event_loop()
    report = await loop.run_in_executor(
        None,
        lambda: generate_learning_report(
            request.session_id,
            request.conversation_history,
            request.kpis_history,
        )
    )

    return _report_to_response(report)