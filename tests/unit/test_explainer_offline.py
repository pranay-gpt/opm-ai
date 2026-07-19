"""Offline tests for explainer module (no LLM calls)."""

from __future__ import annotations

from opm_ai.explainer import explain, generate_quiz, generate_learning_report
from opm_ai.explainer.models import ExplanationLevel


def test_explain_kpi_dict_all_levels():
    """Test explain() with KPI dict at all 3 levels returns valid Explanation."""
    kpis = {
        "days": 1825.0,
        "field_oil_recovery": 1_200_000.0,
        "water_breakthrough_day": 1100.0,
        "max_watercut": 0.85,
        "producer_count": 3,
    }

    for level in ("beginner", "intermediate", "advanced"):
        exp = explain(kpis, level=level)
        assert exp.topic, "Topic should not be empty"
        assert exp.level == level
        assert exp.text, "Explanation text should not be empty"
        assert len(exp.text) > 50, "Explanation should be substantive"
        assert 1 <= len(exp.citations) <= 5, f"Expected 1-5 citations, got {len(exp.citations)}"
        assert 2 <= len(exp.follow_up_questions) <= 3, f"Expected 2-3 follow-ups, got {len(exp.follow_up_questions)}"


def test_explain_free_text():
    """Test explain() with free-text question."""
    exp = explain("why did watercut spike after 3 years?", level="intermediate")
    assert exp.topic == "why did watercut spike after 3 years?"
    assert exp.text
    assert len(exp.citations) >= 1
    assert len(exp.follow_up_questions) >= 2


def test_explain_watercut_topic():
    """Test watercut topic triggers correct template."""
    exp = explain("water breakthrough and watercut behavior", level="advanced")
    assert "buckley" in exp.text.lower() or "fractional flow" in exp.text.lower() or "mobility ratio" in exp.text.lower()


def test_generate_quiz_offline():
    """Test generate_quiz() returns valid Quiz offline."""
    quiz = generate_quiz(
        scenario_summary="5-year waterflood with breakthrough at year 3",
        level="intermediate",
        n_questions=3,
        topic_focus=["waterflood", "watercut"],
    )

    assert quiz.scenario_summary == "5-year waterflood with breakthrough at year 3"
    assert len(quiz.questions) == 3

    for q in quiz.questions:
        assert isinstance(q, object)  # QuizQuestion
        assert q.question
        assert len(q.options) == 4
        assert 0 <= q.correct_index <= 3
        assert q.explanation
        assert q.level == "intermediate"
        assert isinstance(q.topic_tags, tuple)


def test_generate_quiz_exactly_n():
    """Test generate_quiz returns exactly n questions."""
    for n in [3, 4, 5]:
        quiz = generate_quiz("test scenario", n_questions=n)
        assert len(quiz.questions) == n, f"Expected {n} questions, got {len(quiz.questions)}"


def test_generate_learning_report_offline():
    """Test generate_learning_report() with fake conversation."""
    conversation = [
        {"role": "user", "content": "Why did watercut spike at year 3?"},
        {"role": "assistant", "content": "Water breakthrough occurred due to unfavorable mobility ratio..."},
        {"role": "user", "content": "What is fractional flow?"},
        {"role": "assistant", "content": "Fractional flow describes the fraction of water in total flow..."},
        {"role": "user", "content": "How does mobility ratio affect sweep?"},
        {"role": "assistant", "content": "Mobility ratio > 1 causes fingering and poor sweep..."},
        {"role": "user", "content": "Quiz me on waterflood concepts"},
        {"role": "quiz_result", "content": "waterflood:0.8"},
    ]

    report = generate_learning_report("test-session-123", conversation)

    assert report.session_id == "test-session-123"
    assert len(report.topics_covered) >= 1
    assert report.explanations_generated >= 1
    assert report.questions_asked >= 3
    assert "Concepts Covered" in report.markdown
    assert "Questions Asked" in report.markdown
    assert "Suggested Reading" in report.markdown

    # Check quiz scores extracted
    assert report.quiz_scores is not None
    assert "waterflood" in report.quiz_scores


def test_generate_learning_report_detects_topics():
    """Test that topics are detected from conversation."""
    conversation = [
        {"role": "user", "content": "Explain bubble point pressure and PVT tables"},
        {"role": "assistant", "content": "Bubble point is..."},
        {"role": "user", "content": "What about relative permeability Corey exponents?"},
        {"role": "assistant", "content": "Corey correlation uses..."},
    ]

    report = generate_learning_report("topic-test", conversation)

    topic_str = " ".join(report.topics_covered).lower()
    assert "bubble_point" in topic_str or "pvt" in topic_str
    assert "relative_permeability" in topic_str or "relperm" in topic_str


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])