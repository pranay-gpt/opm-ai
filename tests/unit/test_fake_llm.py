"""Tests for the shared FakeLLMClient test fixtures.

These tests cover the helper module itself - not the production LLM client.
They are the contract the rest of the test suite relies on; if any of
these regress, every consumer (extract_parameters_llm, websocket chat
dispatch, summarisation) will silently misbehave in tests.
"""
import json

from opm_ai.llm.testing import (
    FakeLLMClient,
    RecordingFakeLLMClient,
    ScriptedFakeLLMClient,
    make_chat_with_tools_response,
    make_tool_call,
)


def test_fake_llm_client_records_extract_json_call():
    """extract_json records args and returns None by default."""
    client = FakeLLMClient()
    result = client.extract_json("system", "user", schema={"type": "object"})
    assert result is None
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call.method == "extract_json"
    assert call.args == ("system", "user")
    assert call.kwargs == {"schema": {"type": "object"}}


def test_fake_llm_client_chat_records_and_returns_none():
    client = FakeLLMClient()
    assert client.chat([]) is None
    assert client.calls[0].method == "chat"
    assert client.calls[0].args == ([],)


def test_fake_llm_client_chat_with_tools_default_shape():
    """Default chat_with_tools returns the same shape LLMClient returns
    when the SDK gives back no content and no tool_calls. The websocket
    chat route reads both keys, so this is the minimum contract."""
    client = FakeLLMClient()
    result = client.chat_with_tools([], [])
    assert result == {"content": None, "tool_calls": None}
    assert client.calls[0].method == "chat_with_tools"
    assert client.calls[0].args == ([], [])


def test_fake_llm_client_available_true():
    """available defaults to True so callers that gate on
    `getattr(client, 'available', True)` see this client as live."""
    assert FakeLLMClient().available is True


def test_fake_llm_client_calls_are_a_copy():
    """The `calls` property is a snapshot - mutating it must not affect
    later reads of internal state."""
    client = FakeLLMClient()
    client.extract_json("s", "u")
    snapshot = client.calls
    snapshot.clear()
    assert len(client.calls) == 1


def test_scripted_fake_llm_client_replays_in_order():
    """The first call to a method returns the first scripted value; the
    second call returns the second; further calls fall back to None."""
    script = [
        ("extract_json", {"scenario": "depletion"}),
        ("extract_json", None),
    ]
    client = ScriptedFakeLLMClient(script)
    assert client.extract_json("s", "u") == {"scenario": "depletion"}
    assert client.extract_json("s", "u") is None
    # Third call - script exhausted, default.
    assert client.extract_json("s", "u") is None
    # And chat was never scripted - it returns None.
    assert client.chat([]) is None
    assert len(client.calls) == 4


def test_scripted_fake_llm_client_per_method_buckets():
    """Two methods can each have their own scripted queue; one method's
    exhaustion does not affect the other."""
    script = [
        ("chat", "first"),
        ("extract_json", {"k": 1}),
        ("chat", "second"),
    ]
    client = ScriptedFakeLLMClient(script)
    assert client.chat([]) == "first"
    assert client.extract_json("s", "u") == {"k": 1}
    assert client.chat([]) == "second"
    # chat queue exhausted, extract_json queue exhausted -> both None.
    assert client.chat([]) is None
    assert client.extract_json("s", "u") is None


def test_recording_fake_llm_client_always_returns_none():
    """RecordingFakeLLMClient returns the same defaults as FakeLLMClient
    but exists as a separate class so test code can express intent."""
    client = RecordingFakeLLMClient()
    assert client.chat([]) is None
    assert client.chat_with_tools([], []) == {"content": None, "tool_calls": None}
    assert client.extract_json("s", "u") is None
    assert client.summarize_issues(None) is None
    assert len(client.calls) == 4


def test_make_chat_with_tools_response_both_keys():
    """When content and tool_calls are both provided, both keys appear."""
    resp = make_chat_with_tools_response(
        content="thinking...",
        tool_calls=[make_tool_call("lint_deck", {"deck_path": "a.DATA"})],
    )
    assert resp["content"] == "thinking..."
    assert len(resp["tool_calls"]) == 1
    assert resp["tool_calls"][0]["type"] == "function"


def test_make_chat_with_tools_response_content_only():
    """Plain assistant reply - no tool_calls key required."""
    resp = make_chat_with_tools_response(content="ok")
    assert resp == {"content": "ok", "tool_calls": None}


def test_make_chat_with_tools_response_no_args():
    """No content and no tool_calls - the empty-reply shape."""
    resp = make_chat_with_tools_response()
    assert resp == {"content": None, "tool_calls": None}


def test_make_tool_call_arguments_are_json_string():
    """The arguments field is a JSON-encoded string, matching what the
    real OpenAI/Groq SDK returns (and what the websocket route parses
    via json.loads)."""
    tc = make_tool_call("run_simulation", {"deck_path": "x.DATA", "output_dir": "out"})
    assert tc["id"] == "call_test_1"
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "run_simulation"
    decoded = json.loads(tc["function"]["arguments"])
    assert decoded == {"deck_path": "x.DATA", "output_dir": "out"}


def test_make_tool_call_custom_id():
    tc = make_tool_call("lint_deck", {}, call_id="abc123")
    assert tc["id"] == "abc123"