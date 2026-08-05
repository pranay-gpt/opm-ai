"""Reusable LLMClient stand-ins for offline unit tests.

This module is NOT production code. Importing it has no side effects (no
network, no SDK init) - the classes are plain Python and merely expose the
attributes / methods that the LLM client code paths read.

Why hand-rolled instead of unittest.mock?
- The chat-with-tools and extract_json code paths read nested attributes
  (response.choices[0].message.content, tool.function.arguments, ...) and
  duck-typed shape is simpler to read and maintain than nested MagicMocks.
- These classes double as living documentation of the LLMClient surface
  that tests need to satisfy.
- No new test dependency: pytest >=9.1 is the only dev extra.

Where to use:
- `tests/unit/` already has a private FakeClient at
  tests/unit/test_llm_extraction.py:10. Migrate new tests onto the shared
  classes here; leave the local one for now (it has different defaults).

What is exposed:
- FakeLLMClient: drop-in for LLMClient - methods are no-ops by default and
  can be assigned per-test. Use it when the code under test calls multiple
  methods on the same client (chat, extract_json, chat_with_tools).
- ScriptedFakeLLMClient: takes a list of (method_name, return_value) tuples
  and replays them in order. Use it for tests that need different responses
  on each call (e.g. first extract_json invalid JSON, second valid).
- RecordingFakeLLMClient: a thin proxy that records every call and returns
  None - use it to assert "the code under test called extract_json with this
  prompt and no other method."

All three expose `available = True` so the offline short-circuit in
extract_parameters_llm does not apply. The LLMClient's `available` property
is what callers check; overriding it as a class attribute on the subclass
matches that contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class _Call:
    """One recorded call. method + kwargs is enough to assert on."""

    method: str
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)


class FakeLLMClient:
    """LLMClient stand-in. Every public method is overridable per instance.

    Default behaviour:
    - chat() -> None
    - chat_with_tools() -> {"content": None, "tool_calls": None}
    - extract_json() -> None
    - summarize_issues() -> None

    Assign any method on the instance to override, or subclass to bundle
    canned responses. The `_calls` list records every invocation so tests
    can assert on prompt content, kwargs, and call ordering.

    The `available = True` class attribute matches LLMClient.available so
    callers that gate on `getattr(client, "available", True)` see this
    client as live.
    """

    available: bool = True

    def __init__(self) -> None:
        self._calls: list[_Call] = []

    @property
    def calls(self) -> list[_Call]:
        """All recorded calls, oldest first. Read-only view."""
        return list(self._calls)

    def _record(self, method: str, *args: Any, **kwargs: Any) -> None:
        self._calls.append(_Call(method=method, args=args, kwargs=kwargs))

    def chat(self, messages: list[dict]) -> str | None:
        self._record("chat", messages)
        return None

    def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        self._record("chat_with_tools", messages, tools)
        return {"content": None, "tool_calls": None}

    def extract_json(
        self, system_prompt: str, user_prompt: str, schema: dict | None = None
    ) -> dict | None:
        self._record("extract_json", system_prompt, user_prompt, schema=schema)
        return None

    def summarize_issues(self, lint_result: Any) -> str | None:
        self._record("summarize_issues", lint_result)
        return None


class ScriptedFakeLLMClient(FakeLLMClient):
    """FakeLLMClient that replays a scripted list of (method, return).

    Each entry is (method_name, return_value). The first call to that
    method returns the value and consumes the entry; subsequent calls fall
    back to FakeLLMClient defaults (returning None).

    Use for sequential scenarios:
        script = [
            ("extract_json", {"scenario": "5spot"}),  # call 1 -> dict
            ("extract_json", None),                    # call 2 -> None
        ]
        client = ScriptedFakeLLMClient(script)

    To replay specific kwargs (e.g. "only return the scripted value if the
    system prompt contains 'foo'"), subclass and override the method.
    """

    def __init__(self, script: list[tuple[str, Any]]) -> None:
        super().__init__()
        # List of (method_name, [pending_return_values]). A method can appear
        # multiple times; each entry is consumed in order.
        self._pending: dict[str, list[Any]] = {}
        for method, value in script:
            self._pending.setdefault(method, []).append(value)

    def _next(self, method: str) -> Any:
        bucket = self._pending.get(method)
        if bucket:
            return bucket.pop(0)
        return None  # default: behaviour matches FakeLLMClient

    def chat(self, messages: list[dict]) -> str | None:
        self._record("chat", messages)
        return self._next("chat")

    def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        self._record("chat_with_tools", messages, tools)
        return self._next("chat_with_tools")

    def extract_json(
        self, system_prompt: str, user_prompt: str, schema: dict | None = None
    ) -> dict | None:
        self._record("extract_json", system_prompt, user_prompt, schema=schema)
        return self._next("extract_json")

    def summarize_issues(self, lint_result: Any) -> str | None:
        self._record("summarize_issues", lint_result)
        return self._next("summarize_issues")


class RecordingFakeLLMClient(FakeLLMClient):
    """FakeLLMClient that always returns None but records every call.

    Use when the assertion is "the code under test called method X with
    argument Y", not on the return value.
    """

    # All methods inherited; they record and return None by default. No
    # additional override needed - this subclass exists so call sites can
    # be explicit about intent ("I am asserting on call shape, not value").
    pass


def make_chat_with_tools_response(
    content: str | None = None,
    tool_calls: list[dict] | None = None,
) -> dict:
    """Build a chat_with_tools response dict in the same shape LLMClient
    produces from a real SDK response.

    tool_calls entries must already be in the SDK-output shape:
        {"id": "...", "type": "function",
         "function": {"name": "...", "arguments": "<json string>"}}

    Returns: {"content": content, "tool_calls": tool_calls or None}.
    Pass to ScriptedFakeLLMClient via ("chat_with_tools", make_chat_with_tools_response(...)).
    """
    return {"content": content, "tool_calls": tool_calls}


def make_tool_call(name: str, arguments: dict, call_id: str = "call_test_1") -> dict:
    """Build one tool_call dict in the SDK-output shape that LLMClient
    emits (and that downstream route code consumes).
    """
    import json

    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments),
        },
    }