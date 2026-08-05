"""Deterministic websocket tests for the chat tool-calling loop.

Drives /api/chat end-to-end through Starlette's TestClient with the LLM
client monkeypatched to a scripted fake: first a tool call, then a text
reply. Proves the full event protocol (tool_call -> tool_result -> token
-> done) and multi-turn reuse of one connection without any network.
"""

import json

import pytest
from fastapi.testclient import TestClient

import opm_ai.api.routes.chat as chat_routes
from opm_ai.api.server import create_app
from opm_ai.api.session_store import clear_sessions


class ScriptedLLM:
    """Fake LLMClient: returns queued responses in order, then a default
    text reply. Mimics chat_with_tools' contract."""

    available = True

    def __init__(self, script):
        self._script = list(script)

    def chat_with_tools(self, messages, tools):
        if self._script:
            return self._script.pop(0)
        return {"content": "All done.", "tool_calls": None}


@pytest.fixture(autouse=True)
def clean_sessions():
    clear_sessions()
    yield
    clear_sessions()


def _ws_events(ws):
    """Read events until done/error; the server keeps the socket open for
    the next turn."""
    events = []
    while True:
        msg = json.loads(ws.receive_text())
        events.append(msg)
        if msg["type"] in ("done", "error"):
            return events


@pytest.mark.integration
def test_ws_tool_loop_streams_tool_then_text(monkeypatch, tmp_path):
    """One turn: scripted tool call (lint on a real deck) then text; the
    client sees tool_call, tool_result, token, done in order."""
    deck = tmp_path / "loop_test.DATA"
    deck.write_text("RUNSPEC\nTITLE\nt /\n")

    script = [
        {
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "lint_deck",
                        "arguments": json.dumps({"deck_path": str(deck)}),
                    },
                }
            ],
        },
        {"content": "The deck has lint findings.", "tool_calls": None},
    ]
    monkeypatch.setattr(chat_routes, "LLMClient", lambda: ScriptedLLM(script))

    client = TestClient(create_app())
    with client.websocket_connect("/api/chat") as ws:
        ws.send_text(json.dumps({
            "session_id": "ws-loop-1",
            "messages": [{"role": "user", "content": "lint my deck"}],
        }))
        events = _ws_events(ws)

    kinds = [e["type"] for e in events]
    assert kinds == ["tool_call", "tool_result", "token", "done"]
    assert events[0]["tool_name"] == "lint_deck"
    assert events[1]["result"]["deck_path"] == str(deck)
    assert events[2]["content"] == "The deck has lint findings."


@pytest.mark.integration
def test_ws_multi_turn_same_connection(monkeypatch):
    """Two turns on ONE connection: each gets its own done; history grows
    server-side (second reply sees the first)."""
    script = [
        {"content": "First reply.", "tool_calls": None},
        {"content": "Second reply.", "tool_calls": None},
    ]
    fake = ScriptedLLM(script)
    monkeypatch.setattr(chat_routes, "LLMClient", lambda: fake)

    client = TestClient(create_app())
    with client.websocket_connect("/api/chat") as ws:
        ws.send_text(json.dumps({
            "session_id": "ws-loop-2",
            "messages": [{"role": "user", "content": "hello"}],
        }))
        first = _ws_events(ws)

        # Frontend sends its full message list; only the trailing user
        # message is new.
        ws.send_text(json.dumps({
            "session_id": "ws-loop-2",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "First reply."},
                {"role": "user", "content": "again"},
            ],
        }))
        second = _ws_events(ws)

    assert [e["type"] for e in first] == ["token", "done"]
    assert first[0]["content"] == "First reply."
    assert [e["type"] for e in second] == ["token", "done"]
    assert second[0]["content"] == "Second reply."


@pytest.mark.integration
def test_ws_replay_without_new_user_message_is_ignored(monkeypatch):
    """A reconnect replay (message list ending in an assistant message)
    must not trigger a new completion."""
    calls = {"n": 0}

    class CountingLLM(ScriptedLLM):
        def chat_with_tools(self, messages, tools):
            calls["n"] += 1
            return super().chat_with_tools(messages, tools)

    fake = CountingLLM([{"content": "Reply.", "tool_calls": None}])
    monkeypatch.setattr(chat_routes, "LLMClient", lambda: fake)

    client = TestClient(create_app())
    with client.websocket_connect("/api/chat") as ws:
        ws.send_text(json.dumps({
            "session_id": "ws-loop-3",
            "messages": [{"role": "user", "content": "hi"}],
        }))
        _ws_events(ws)
        assert calls["n"] == 1

        # Replay ending in assistant message: server should wait, not call
        # the LLM again. Send a real follow-up right after and confirm
        # exactly one more completion happens.
        ws.send_text(json.dumps({
            "session_id": "ws-loop-3",
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "Reply."},
            ],
        }))
        ws.send_text(json.dumps({
            "session_id": "ws-loop-3",
            "messages": [{"role": "user", "content": "follow-up"}],
        }))
        _ws_events(ws)

    assert calls["n"] == 2


@pytest.mark.integration
def test_ws_offline_provider_sends_error(monkeypatch):
    """Offline client yields a structured error with both message and
    content fields (frontend reads message)."""

    class OfflineLLM:
        available = False

    monkeypatch.setattr(chat_routes, "LLMClient", OfflineLLM)

    client = TestClient(create_app())
    with client.websocket_connect("/api/chat") as ws:
        ws.send_text(json.dumps({
            "session_id": "ws-loop-4",
            "messages": [{"role": "user", "content": "hi"}],
        }))
        msg = json.loads(ws.receive_text())

    assert msg["type"] == "error"
    assert "offline" in msg["message"]
    assert msg["content"] == msg["message"]


@pytest.mark.integration
def test_ws_rejects_oversized_frame(monkeypatch):
    """A frame larger than WS_MAX_FRAME_BYTES is rejected with a
    payload_too_large error and the connection stays open for the next
    valid turn."""
    fake = ScriptedLLM([{"content": "ok", "tool_calls": None}])
    monkeypatch.setattr(chat_routes, "LLMClient", lambda: fake)

    # Build a frame above the 64 KB limit by padding a long user message.
    huge = "A" * (chat_routes.WS_MAX_FRAME_BYTES + 1024)
    bad_frame = json.dumps({
        "session_id": "ws-loop-big",
        "messages": [{"role": "user", "content": huge}],
    })
    assert len(bad_frame.encode("utf-8")) > chat_routes.WS_MAX_FRAME_BYTES

    client = TestClient(create_app())
    with client.websocket_connect("/api/chat") as ws:
        ws.send_text(bad_frame)
        err = json.loads(ws.receive_text())
        assert err["type"] == "error"
        assert err["code"] == "payload_too_large"

        # Connection still alive: a real, small request now gets a normal
        # reply.
        ws.send_text(json.dumps({
            "session_id": "ws-loop-big",
            "messages": [{"role": "user", "content": "now what"}],
        }))
        events = _ws_events(ws)
    assert [e["type"] for e in events] == ["token", "done"]


@pytest.mark.integration
def test_ws_rejects_malformed_payload(monkeypatch):
    """Garbage JSON and schema-invalid frames yield invalid_payload
    errors; the connection is preserved for the next turn."""
    fake = ScriptedLLM([{"content": "ok", "tool_calls": None}])
    monkeypatch.setattr(chat_routes, "LLMClient", lambda: fake)

    client = TestClient(create_app())
    with client.websocket_connect("/api/chat") as ws:
        # 1) Not JSON at all
        ws.send_text("this is not json {{{")
        err = json.loads(ws.receive_text())
        assert err["type"] == "error"
        assert err["code"] == "invalid_payload"

        # 2) JSON but wrong shape (missing session_id)
        ws.send_text(json.dumps({"messages": []}))
        err = json.loads(ws.receive_text())
        assert err["type"] == "error"
        assert err["code"] == "invalid_payload"

        # 3) Real request after the errors still works
        ws.send_text(json.dumps({
            "session_id": "ws-loop-malformed",
            "messages": [{"role": "user", "content": "hi"}],
        }))
        events = _ws_events(ws)
    assert [e["type"] for e in events] == ["token", "done"]


@pytest.mark.integration
def test_compact_tool_result_shrinks_large_payloads():
    """build_deck and get_kpis results are compacted for LLM history."""
    big_deck = {"deck": "X" * 50000, "lint": {"passed": True, "errors": []}}
    compact = chat_routes.compact_tool_result("build_deck", big_deck)
    assert len(json.dumps(compact)) < 1000
    assert compact["lint"]["passed"] is True
    assert compact["deck_chars"] == 50000

    kpis = {"kpis": {"days": 720.0}, "plots": {"production": "Y" * 100000}}
    compact = chat_routes.compact_tool_result("get_kpis", kpis)
    assert len(json.dumps(compact)) < 500
    assert compact["kpis"]["days"] == 720.0

    # Other tools pass through untouched
    other = {"job_id": "abc", "status": "pending"}
    assert chat_routes.compact_tool_result("run_simulation", other) == other


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
