"""Learning report generation for the educational explainer.

This module implements generate_learning_report() to create end-of-session summaries.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from opm_ai.explainer.models import Citation, LearningReport
from opm_ai.explainer.retrieve import retrieve_chunks
from opm_ai.llm.client import LLMClient


# ---- Topic Keywords for Extraction ----

TOPIC_KEYWORDS = {
    "waterflood": ["waterflood", "water flood", "waterflooding", "injection", "injector", "5-spot", "pattern flood"],
    "watercut": ["watercut", "water cut", "breakthrough", "wct", "water breakthrough", "fractional flow"],
    "pvt": ["pvt", "bubble point", "bubblepoint", "rs ", "gor", "formation volume", "bo ", "bg ", "solution gas"],
    "relative_permeability": ["relative permeability", "relperm", "corey", "krw", "kro", "krg", "endpoint", "exponent"],
    "well_control": ["well control", "rate control", "bhp", "wconprod", "wconinje", "constraint", "thp", "vfp"],
    "material_balance": ["material balance", "mb ", "ooip", "drive mechanism", "depletion", "aquifer"],
    "depletion_drive": ["depletion", "solution gas drive", "gas drive", "primary recovery"],
    "timestepping": ["timestep", "time step", "chop", "convergence", "newton", "tuning", "cpr", "amg"],
    "buckley_leverett": ["buckley", "leverett", "fractional flow", "shock front", "welge tangent"],
    "spe1": ["spe1", "spe 1", "odeh", "benchmark", "comparative solution"],
    "grid": ["grid", "corner point", "cartesian", "permx", "permy", "permz", "actnum"],
    "pvt_tables": ["pvto", "pvtg", "pvtw", "rss", "pvt table", "interpolation"],
    "well_performance": ["well performance", "inflow", "productivity index", "pi ", "skin", "wellbore"],
    "recovery_factor": ["recovery factor", "rf ", "oil recovery", "eor", "enhanced recovery"],
}


def _extract_topics(text: str) -> list[str]:
    """Extract topic tags from text using keyword matching."""
    text_lower = text.lower()
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            topics.append(topic)
    return topics


def _extract_quiz_scores(conversation_history: list[dict]) -> dict[str, float] | None:
    """Extract quiz scores from conversation history if present.

    Convention: messages with role "quiz_result" and content "topic:score"
    """
    scores = {}
    for msg in conversation_history:
        if msg.get("role") == "quiz_result" and isinstance(msg.get("content"), str):
            content = msg["content"]
            if ":" in content:
                topic, score_str = content.split(":", 1)
                try:
                    scores[topic.strip()] = float(score_str.strip())
                except ValueError:
                    pass
    return scores if scores else None


def _cluster_conversation_topics(messages: list[dict]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract topics and key concepts from conversation history."""
    user_messages = [m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)]

    all_topics = []
    for msg in user_messages:
        all_topics.extend(_extract_topics(msg))

    # Count frequencies
    topic_counts = Counter(all_topics)
    topics_covered = tuple(topic for topic, _ in topic_counts.most_common())

    # Key concepts = topics + extracted noun phrases from questions
    key_concepts = list(topics_covered)
    # Add some specific terms from messages
    for msg in user_messages[:10]:  # First 10 questions
        words = re.findall(r"\b[a-z]{5,}\b", msg.lower())
        for w in words[:3]:
            if w not in key_concepts and w not in {"water", "oil", "well", "field", "rate"}:
                key_concepts.append(w)

    return topics_covered, tuple(key_concepts[:15])


# ---- LLM-based Report Generation ----

REPORT_SYSTEM_PROMPT = """You are an expert reservoir engineering educator writing a learning report.

Write a concise Session Summary paragraph (3-5 sentences) summarizing what the student learned.
Focus on the key concepts covered and the progression of understanding.
Do not include markdown formatting in the summary paragraph - plain text only."""

REPORT_USER_PROMPT = """Session topics: {topics}
User questions: {questions}
Key concepts: {concepts}

Write a Session Summary paragraph."""


def _build_report_prompt(topics: tuple[str, ...], questions: list[str], concepts: tuple[str, ...]) -> list[dict]:
    return [
        {"role": "system", "content": REPORT_SYSTEM_PROMPT},
        {"role": "user", "content": REPORT_USER_PROMPT.format(
            topics=", ".join(topics),
            questions="; ".join(questions[:5]),
            concepts=", ".join(concepts),
        )},
    ]


# ---- Offline Fallback Report Template ----

OFFLINE_REPORT_TEMPLATE = """# Learning Report - Session {session_id}

## Session Summary
{session_summary}

## Concepts Covered
{concepts_list}

## Questions Asked
{questions_list}

## Key Concepts
{key_concepts_list}

## Suggested Reading
{suggested_reading}
"""


def _generate_offline_report(
    session_id: str,
    conversation_history: list[dict],
    kpis_history: list[dict] | None,
) -> LearningReport:
    """Generate report without LLM (offline fallback)."""
    topics_covered, key_concepts = _cluster_conversation_topics(conversation_history)

    user_messages = [m["content"] for m in conversation_history if m.get("role") == "user" and isinstance(m.get("content"), str)]
    questions_asked = len(user_messages)

    # Get citations for top topics
    citations: list[Citation] = []
    for topic in topics_covered[:5]:
        topic_citations = retrieve_chunks(topic, k=1, level="intermediate")
        citations.extend(topic_citations)

    # Deduplicate citations
    seen = set()
    unique_citations = []
    for c in citations:
        if c.source_id not in seen:
            seen.add(c.source_id)
            unique_citations.append(c)
    citations = tuple(unique_citations[:10])

    # Extract quiz scores if any
    quiz_scores = _extract_quiz_scores(conversation_history)

    # Build markdown
    session_summary = f"Session covered {len(topics_covered)} topics with {questions_asked} questions. " \
                      f"Key areas: {', '.join(topics_covered[:5])}."

    concepts_md = "\n".join([f"- {t}" for t in topics_covered]) or "- (none detected)"
    questions_md = "\n".join([f"- {q[:100]}" for q in user_messages[:10]]) or "- (none)"
    key_concepts_md = "\n".join([f"- {c}" for c in key_concepts]) or "- (none)"
    suggested_md = "\n".join([f"- {c.title} ({c.source_id})" for c in citations[:5]]) or "- (no citations)"

    markdown = OFFLINE_REPORT_TEMPLATE.format(
        session_id=session_id,
        session_summary=session_summary,
        concepts_list=concepts_md,
        questions_list=questions_md,
        key_concepts_list=key_concepts_md,
        suggested_reading=suggested_md,
    )

    return LearningReport(
        session_id=session_id,
        topics_covered=topics_covered,
        explanations_generated=sum(1 for m in conversation_history if m.get("role") == "assistant"),
        questions_asked=questions_asked,
        quiz_scores=quiz_scores,
        key_concepts=key_concepts,
        citations_used=citations,
        markdown=markdown,
    )


# ---- Public API ----

def generate_learning_report(
    session_id: str,
    conversation_history: list[dict],
    kpis_history: list[dict] | None = None,
) -> LearningReport:
    """
    Generate a learning report from a conversation session.

    Args:
        session_id: Unique session identifier
        conversation_history: List of {"role": "user|assistant|quiz_result", "content": "..."}
        kpis_history: Optional list of KPI dicts from simulation runs

    Returns:
        LearningReport with markdown summary and structured data
    """
    llm = LLMClient()

    # Try LLM for session summary
    topics_covered, key_concepts = _cluster_conversation_topics(conversation_history)
    user_messages = [m["content"] for m in conversation_history if m.get("role") == "user" and isinstance(m.get("content"), str)]

    session_summary = None
    if llm.available:
        try:
            messages = _build_report_prompt(topics_covered, user_messages, key_concepts)
            response = llm.chat(messages)
            if response:
                session_summary = response.strip()
        except Exception:
            pass

    # Generate report (offline for citations, with optional LLM summary)
    report = _generate_offline_report(session_id, conversation_history, kpis_history)

    # Replace session summary with LLM version if available
    if session_summary:
        # Rebuild markdown with LLM summary
        citations = report.citations_used
        concepts_md = "\n".join([f"- {t}" for t in report.topics_covered]) or "- (none detected)"
        questions_md = "\n".join([f"- {q[:100]}" for q in user_messages[:10]]) or "- (none)"
        key_concepts_md = "\n".join([f"- {c}" for c in report.key_concepts]) or "- (none)"
        suggested_md = "\n".join([f"- {c.title} ({c.source_id})" for c in citations[:5]]) or "- (no citations)"

        markdown = OFFLINE_REPORT_TEMPLATE.format(
            session_id=session_id,
            session_summary=session_summary,
            concepts_list=concepts_md,
            questions_list=questions_md,
            key_concepts_list=key_concepts_md,
            suggested_reading=suggested_md,
        )

        report = LearningReport(
            session_id=report.session_id,
            topics_covered=report.topics_covered,
            explanations_generated=report.explanations_generated,
            questions_asked=report.questions_asked,
            quiz_scores=report.quiz_scores,
            key_concepts=report.key_concepts,
            citations_used=report.citations_used,
            markdown=markdown,
        )

    return report