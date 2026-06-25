"""
LLM router for OPM-AI.

Routes requests to either Groq or NVIDIA NIM using the OpenAI-compatible
API surface. Both are free tiers. NVIDIA NIM hosts Nemotron-Ultra-253B.

Usage:
    from opm_ai.chat.llm_router import chat
    response, tool_calls = chat(messages, session, stream=True)
"""

from __future__ import annotations

import json
import os
from typing import Any, Generator, List, Optional, Tuple

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

from opm_ai.chat.providers import get_provider, ProviderConfig
from opm_ai.chat.tools import TOOL_SCHEMAS, dispatch


MAX_TOOL_ROUNDS = 5  # prevent infinite tool loops


class LLMRouter:
    """Stateless LLM router. Session state is held by the caller (Streamlit)."""

    def __init__(self, provider_name: str, model: Optional[str] = None):
        self.provider: ProviderConfig = get_provider(provider_name)
        self.model: str = model or self.provider.default_model
        if OpenAI is None:
            raise RuntimeError("openai package not installed. Run: pip install openai")
        api_key = os.getenv(self.provider.api_key_env, "")
        if not api_key:
            raise ValueError(
                f"API key not found. Set the {self.provider.api_key_env} environment variable."
            )
        self.client = OpenAI(base_url=self.provider.base_url, api_key=api_key)

    # ─── Main entry point ────────────────────────────────────────────────────

    def chat(
        self,
        messages: List[dict],
        session: dict,
        stream: bool = True,
    ) -> Generator[str, None, None]:
        """
        Send messages to the LLM, handle tool calls automatically,
        and yield text tokens for streaming display.
        """
        working_messages = list(messages)

        for _round in range(MAX_TOOL_ROUNDS):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=working_messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                stream=False,  # always False so we can inspect tool calls
                temperature=0.2,
                max_tokens=4096,
            )

            choice = response.choices[0]
            msg = choice.message

            # ── Tool call round ──
            if msg.tool_calls:
                working_messages.append(msg.model_dump(exclude_unset=True))
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    session["last_tool_called"] = tool_name
                    result_str = dispatch(tool_name, args, session)
                    working_messages.append(
                        {"role": "tool", "tool_call_id": tc.id, "content": result_str}
                    )
                # loop: send tool results back to LLM
                continue

            # ── Final text response ──
            text = msg.content or ""
            if stream:
                # Simulate streaming word-by-word for smooth UX
                words = text.split(" ")
                for i, word in enumerate(words):
                    yield word + (" " if i < len(words) - 1 else "")
            else:
                yield text
            return

        # Guard: too many tool rounds
        yield "\n\n⚠️ Reached maximum tool call depth. Please rephrase your question."


def build_router(session: dict) -> LLMRouter:
    """Convenience factory using session state."""
    return LLMRouter(
        provider_name=session.get("llm_provider", "groq"),
        model=session.get("selected_model"),
    )
