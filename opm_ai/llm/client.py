"""LLM client with Groq, OpenAI-compatible, and offline fallback."""

from typing import Optional

from opm_ai.settings import settings


class LLMClient:
    """LLM client supporting Groq, OpenAI-compatible endpoints, and offline mode."""

    def __init__(self) -> None:
        """Initialize client. Never raises; falls back to offline mode if no keys."""
        self._groq_client = None
        self._openai_client = None
        self._available = False
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize available clients based on available API keys."""
        # Try Groq
        if settings.groq_api_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=settings.groq_api_key)
                self._available = True
            except Exception:
                self._groq_client = None

        # Try OpenAI-compatible (including NVIDIA NIM)
        if settings.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                )
                self._available = True
            except Exception:
                self._openai_client = None

        # If neither available, offline mode
        if not self._groq_client and not self._openai_client:
            self._available = False

    @property
    def available(self) -> bool:
        """Return True if an LLM provider is available."""
        return self._available

    def chat(self, messages: list[dict]) -> str | None:
        """
        Send chat messages to LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            Response string, or None if offline/unavailable.
        """
        if not self._available:
            return None

        # Try Groq first if available
        if self._groq_client:
            try:
                response = self._groq_client.chat.completions.create(
                    model=settings.groq_model,
                    messages=messages,
                    temperature=0.1,
                )
                return response.choices[0].message.content
            except Exception:
                pass  # Fall through to OpenAI

        # Try OpenAI-compatible
        if self._openai_client:
            try:
                response = self._openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    temperature=0.1,
                )
                return response.choices[0].message.content
            except Exception:
                pass

        return None

    def summarize_issues(self, issues: list) -> str | None:
        """
        Summarize lint issues as a student-friendly block comment.

        Renders opm_ai/linter/prompts/summarize.j2 as the system prompt and
        sends the structured issues as the user message.

        Args:
            issues: List of LintIssue objects.

        Returns:
            Summary string, or None if offline/unavailable/error.
        """
        if not self._available or not issues:
            return None

        try:
            from pathlib import Path
            prompt_path = (
                Path(__file__).parent.parent / "linter" / "prompts" / "summarize.j2"
            )
            system_prompt = prompt_path.read_text(encoding="utf-8")

            issue_lines = [
                f"- [{i.severity}] {i.section or '?'}/{i.keyword or '?'} "
                f"(line {i.line if i.line is not None else '?'}): {i.message}"
                for i in issues
            ]
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "\n".join(issue_lines)},
            ]
            return self.chat(messages)
        except Exception:
            return None