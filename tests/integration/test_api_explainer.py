"""Integration tests for explainer API endpoints (offline, no LLM calls)."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from opm_ai.api.server import create_app
from opm_ai.explainer.models import ExplanationLevel


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient for integration tests."""
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def mock_llm_client():
    """Mock LLM client to return None (offline mode) for all tests."""
    with patch("opm_ai.explainer.explainer.LLMClient") as mock_llm:
        mock_instance = MagicMock()
        mock_instance.available = False
        mock_instance.chat.return_value = None
        mock_instance.chat_with_tools.return_value = {"content": None, "tool_calls": None}
        mock_llm.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_quiz_llm():
    """Mock LLM client for quiz generation to return None (offline mode)."""
    with patch("opm_ai.explainer.quiz.LLMClient") as mock_llm:
        mock_instance = MagicMock()
        mock_instance.available = False
        mock_instance.chat.return_value = None
        mock_llm.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_report_llm():
    """Mock LLM client for learning report to return None (offline mode)."""
    with patch("opm_ai.explainer.report.LLMClient") as mock_llm:
        mock_instance = MagicMock()
        mock_instance.available = False
        mock_instance.chat.return_value = None
        mock_llm.return_value = mock_instance
        yield mock_instance


class TestExplainEndpoint:
    """Tests for POST /api/explain"""

    def test_explain_with_topic(self, client):
        """POST /api/explain with topic -> 200, non-empty text, 1-5 citations, level echoed."""
        response = client.post("/api/explain", json={
            "topic": "why did watercut spike after 3 years?",
            "level": "intermediate"
        })

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert data["topic"] == "why did watercut spike after 3 years?"
        assert data["level"] == "intermediate"
        assert data["text"], "Explanation text should not be empty"
        assert len(data["text"]) > 50, "Explanation should be substantive"
        assert 1 <= len(data["citations"]) <= 5, f"Expected 1-5 citations, got {len(data['citations'])}"
        assert 2 <= len(data["follow_up_questions"]) <= 3, f"Expected 2-3 follow-ups, got {len(data['follow_up_questions'])}"

        # Verify citation structure
        for citation in data["citations"]:
            assert "source_id" in citation
            assert "title" in citation
            assert "url_or_path" in citation
            assert "snippet" in citation

    def test_explain_with_kpis(self, client):
        """POST /api/explain with KPIs dict -> 200, non-empty text."""
        response = client.post("/api/explain", json={
            "kpis": {
                "days": 720,
                "field_oil_recovery": 360000,
                "water_breakthrough_day": 400,
                "max_watercut": 0.6,
                "producer_count": 1
            },
            "level": "beginner"
        })

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert data["level"] == "beginner"
        assert data["text"], "Explanation text should not be empty"
        assert len(data["text"]) > 50
        assert 1 <= len(data["citations"]) <= 5
        assert 2 <= len(data["follow_up_questions"]) <= 3

    def test_explain_with_both_topic_and_kpis_returns_422(self, client):
        """POST /api/explain with both topic and kpis -> 422."""
        response = client.post("/api/explain", json={
            "topic": "water breakthrough",
            "kpis": {"days": 100, "field_oil_recovery": 1000},
            "level": "intermediate"
        })

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "both" in data["detail"].lower() or "either" in data["detail"].lower()

    def test_explain_with_neither_topic_nor_kpis_returns_422(self, client):
        """POST /api/explain with neither topic nor kpis -> 422."""
        response = client.post("/api/explain", json={
            "level": "intermediate"
        })

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data

    def test_explain_all_levels(self, client):
        """Test all three explanation levels."""
        for level in ("beginner", "intermediate", "advanced"):
            response = client.post("/api/explain", json={
                "topic": "water breakthrough",
                "level": level
            })
            assert response.status_code == 200, f"Level {level} failed: {response.text}"
            data = response.json()
            assert data["level"] == level
            assert data["text"]


class TestQuizEndpoint:
    """Tests for POST /api/quiz"""

    def test_quiz_basic(self, client):
        """POST /api/quiz with scenario -> 200, exactly 3 questions, 4 options each, correct_index 0-3."""
        response = client.post("/api/quiz", json={
            "scenario_summary": "5-year waterflood with breakthrough at year 3",
            "level": "intermediate",
            "n_questions": 3
        })

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert data["scenario_summary"] == "5-year waterflood with breakthrough at year 3"
        assert len(data["questions"]) == 3, f"Expected 3 questions, got {len(data['questions'])}"

        for q in data["questions"]:
            assert "question" in q
            assert q["question"], "Question text should not be empty"
            assert "options" in q
            assert len(q["options"]) == 4, f"Expected 4 options, got {len(q['options'])}"
            assert "correct_index" in q
            assert 0 <= q["correct_index"] <= 3, f"correct_index should be 0-3, got {q['correct_index']}"
            assert "explanation" in q
            assert q["explanation"], "Explanation should not be empty"
            assert "level" in q
            assert q["level"] == "intermediate"
            assert "topic_tags" in q
            assert isinstance(q["topic_tags"], list)

    def test_quiz_custom_n_questions(self, client):
        """Test quiz with different n_questions values."""
        for n in [1, 3, 5, 10]:
            response = client.post("/api/quiz", json={
                "scenario_summary": "Test scenario",
                "n_questions": n
            })
            assert response.status_code == 200, f"n_questions={n} failed: {response.text}"
            data = response.json()
            assert len(data["questions"]) == n, f"Expected {n} questions, got {len(data['questions'])}"

    def test_quiz_with_topic_focus(self, client):
        """Test quiz with topic_focus filter."""
        response = client.post("/api/quiz", json={
            "scenario_summary": "Waterflood with water breakthrough",
            "topic_focus": ["waterflood", "watercut"]
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["questions"]) >= 1


class TestLearningReportEndpoint:
    """Tests for POST /api/learning-report"""

    def test_learning_report_basic(self, client):
        """POST /api/learning-report with 6-message conversation -> 200, markdown contains 'Concepts Covered'."""
        conversation = [
            {"role": "user", "content": "Why did watercut spike at year 3?"},
            {"role": "assistant", "content": "Water breakthrough occurred due to unfavorable mobility ratio..."},
            {"role": "user", "content": "What is fractional flow theory?"},
            {"role": "assistant", "content": "Fractional flow describes the fraction of water in total flow..."},
            {"role": "user", "content": "How does mobility ratio affect sweep?"},
            {"role": "assistant", "content": "Mobility ratio > 1 causes fingering and poor sweep efficiency..."},
        ]

        response = client.post("/api/learning-report", json={
            "session_id": "test-session-123",
            "conversation_history": conversation,
            "kpis_history": None
        })

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        assert data["session_id"] == "test-session-123"
        assert len(data["topics_covered"]) >= 1, "Should detect at least one topic"
        assert data["explanations_generated"] >= 1, "Should count assistant messages"
        assert data["questions_asked"] == 3, "Should count 3 user questions"
        assert "Concepts Covered" in data["markdown"], "Markdown should contain 'Concepts Covered'"
        assert "Questions Asked" in data["markdown"], "Markdown should contain 'Questions Asked'"
        assert "Suggested Reading" in data["markdown"], "Markdown should contain 'Suggested Reading'"

    def test_learning_report_with_quiz_scores(self, client):
        """Test learning report extracts quiz scores from conversation."""
        conversation = [
            {"role": "user", "content": "Quiz me on waterflood"},
            {"role": "assistant", "content": "Here are 3 questions..."},
            {"role": "quiz_result", "content": "waterflood:0.8"},
            {"role": "quiz_result", "content": "recovery:0.6"},
        ]

        response = client.post("/api/learning-report", json={
            "session_id": "quiz-test-456",
            "conversation_history": conversation,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["quiz_scores"] is not None
        assert "waterflood" in data["quiz_scores"]
        assert data["quiz_scores"]["waterflood"] == 0.8
        assert "recovery" in data["quiz_scores"]
        assert data["quiz_scores"]["recovery"] == 0.6

    def test_learning_report_detects_topics(self, client):
        """Test that topics are detected from conversation."""
        conversation = [
            {"role": "user", "content": "Explain bubble point pressure and PVT tables"},
            {"role": "assistant", "content": "Bubble point is..."},
            {"role": "user", "content": "What about relative permeability Corey exponents?"},
            {"role": "assistant", "content": "Corey correlation uses..."},
        ]

        response = client.post("/api/learning-report", json={
            "session_id": "topic-test-789",
            "conversation_history": conversation,
        })

        assert response.status_code == 200
        data = response.json()
        topic_str = " ".join(data["topics_covered"]).lower()
        assert "bubble_point" in topic_str or "pvt" in topic_str
        assert "relative_permeability" in topic_str or "relperm" in topic_str


class TestResponseSerialization:
    """Tests that response JSON serializes cleanly (no NaN, tuples become lists)."""

    def test_explain_response_no_nan_no_tuples(self, client):
        """Explain response contains no NaN and all sequences are lists."""
        response = client.post("/api/explain", json={
            "topic": "water breakthrough",
            "level": "advanced"
        })
        assert response.status_code == 200
        data = response.json()

        # Verify JSON serialization (will raise if NaN present)
        import json
        json.dumps(data)

        # Check follow_up_questions is list, not tuple
        assert isinstance(data["follow_up_questions"], list)

        # Check citations is list of dicts
        assert isinstance(data["citations"], list)
        for c in data["citations"]:
            assert isinstance(c, dict)

    def test_quiz_response_no_nan_no_tuples(self, client):
        """Quiz response contains no NaN and all sequences are lists."""
        response = client.post("/api/quiz", json={
            "scenario_summary": "Test scenario",
            "n_questions": 3
        })
        assert response.status_code == 200
        data = response.json()

        import json
        json.dumps(data)

        assert isinstance(data["questions"], list)
        for q in data["questions"]:
            assert isinstance(q["options"], list)
            assert len(q["options"]) == 4
            assert isinstance(q["topic_tags"], list)

    def test_learning_report_response_no_nan_no_tuples(self, client):
        """Learning report response contains no NaN and all sequences are lists."""
        response = client.post("/api/learning-report", json={
            "session_id": "serial-test",
            "conversation_history": [
                {"role": "user", "content": "Test question"},
                {"role": "assistant", "content": "Test answer"},
            ],
        })
        assert response.status_code == 200
        data = response.json()

        import json
        json.dumps(data)

        assert isinstance(data["topics_covered"], list)
        assert isinstance(data["key_concepts"], list)
        assert isinstance(data["citations_used"], list)
        for c in data["citations_used"]:
            assert isinstance(c, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])