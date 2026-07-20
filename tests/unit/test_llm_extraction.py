"""Tests for LLM-based parameter extraction (fully offline, fake clients)."""
import pytest

from opm_ai.builder.builder import build_deck
from opm_ai.builder.extract import extract_parameters_llm
from opm_ai.builder.models import ModelSpec, ScheduleEvent
from opm_ai.llm.client import LLMClient


class FakeClient:
    """Stand-in for LLMClient: canned extract_json responses, no network."""

    def __init__(self, response):
        self._response = response
        self.available = True
        self.calls = []

    def extract_json(self, system_prompt, user_prompt, schema=None):
        self.calls.append((system_prompt, user_prompt))
        return self._response


def test_extract_llm_valid_json():
    """Valid dict from client -> ModelSpec with expected fields."""
    fake = FakeClient({
        "scenario": "5spot_waterflood",
        "reservoir": {"nx": 20, "ny": 20, "nz": 3},
        "wells": [
            {"name": "INJ", "well_type": "INJ", "i": 11, "j": 11, "k1": 1, "k2": 3,
             "inject_fluid": "WATER", "inject_rate": 5000.0},
            {"name": "PROD1", "well_type": "PROD", "i": 1, "j": 1, "k1": 1, "k2": 3},
        ],
    })
    spec = extract_parameters_llm("20x20x3 five spot waterflood", client=fake)
    assert isinstance(spec, ModelSpec)
    assert spec.scenario == "5spot_waterflood"
    assert spec.reservoir.nx == 20
    assert spec.reservoir.nz == 3
    assert len(spec.wells) == 2
    assert spec.wells[0].inject_rate == 5000.0
    # The rendered system prompt embeds the schema and the rules
    system_prompt, user_prompt = fake.calls[0]
    assert "ModelSpec" in system_prompt
    assert "1-based" in system_prompt
    assert user_prompt == "20x20x3 five spot waterflood"


def test_extract_llm_schema_invalid_returns_none():
    """Schema-invalid dict (porosity out of range) -> None."""
    fake = FakeClient({"reservoir": {"nx": 10, "ny": 10, "nz": 3, "porosity": 5.0}})
    assert extract_parameters_llm("bad porosity case", client=fake) is None


def test_extract_llm_client_none_response_returns_none():
    """None from client (offline/parse failure) -> None."""
    fake = FakeClient(None)
    assert extract_parameters_llm("anything", client=fake) is None


def test_extract_llm_unavailable_client_returns_none():
    """Client reporting available=False -> None without calling extract_json."""
    fake = FakeClient({"scenario": "depletion"})
    fake.available = False
    assert extract_parameters_llm("anything", client=fake) is None
    assert fake.calls == []


def test_build_deck_use_llm_offline_falls_back():
    """build_deck(use_llm=True) with provider offline uses the regex path
    and still returns a lint-passing deck."""
    deck_string, lint_result = build_deck(
        "10x10x3 grid, simple depletion, one producer", use_llm=True
    )
    assert "RUNSPEC" in deck_string
    assert "SCHEDULE" in deck_string
    assert lint_result.passed


def test_extract_json_offline_returns_none():
    """LLMClient.extract_json is None when no provider is configured."""
    client = LLMClient()
    if client.available:
        pytest.skip("live LLM provider configured; offline behavior not testable")
    assert client.extract_json("system", "user") is None


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeSDKClient:
    """Mimics the groq/openai chat.completions.create surface."""

    def __init__(self, contents):
        self._contents = list(contents)
        self.requests = []

        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.requests.append(kwargs)
                return _FakeResponse(outer._contents.pop(0))

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def _client_with_fake_sdk(contents):
    client = LLMClient()
    client._available = True
    client._groq_client = _FakeSDKClient(contents)
    return client


def test_extract_json_parses_valid_content():
    client = _client_with_fake_sdk(['{"scenario": "depletion"}'])
    assert client.extract_json("sys", "user") == {"scenario": "depletion"}
    request = client._groq_client.requests[0]
    assert request["response_format"] == {"type": "json_object"}


def test_extract_json_repair_retry():
    """Invalid JSON first, valid on the single repair retry."""
    client = _client_with_fake_sdk(["not json {", '{"scenario": "wag"}'])
    assert client.extract_json("sys", "user") == {"scenario": "wag"}
    assert len(client._groq_client.requests) == 2
    retry_messages = client._groq_client.requests[1]["messages"]
    assert "valid JSON" in retry_messages[-1]["content"]


def test_extract_json_repair_fails_returns_none():
    """Invalid JSON twice -> None, never raises."""
    client = _client_with_fake_sdk(["not json {", "still not json"])
    assert client.extract_json("sys", "user") is None


def test_extract_json_non_dict_returns_none():
    """A JSON array is valid JSON but not an object -> None."""
    client = _client_with_fake_sdk(['[1, 2, 3]'])
    assert client.extract_json("sys", "user") is None


def test_schedule_event_defaults():
    """ScheduleEvent (Stage D placeholder) validates with all-default fields."""
    event = ScheduleEvent()
    assert event.date is None
    assert event.tstep_days is None
    assert event.actions == []
    spec = ModelSpec(schedule=[ScheduleEvent(tstep_days=30.0, actions=["WELOPEN"])])
    assert spec.schedule[0].tstep_days == 30.0
