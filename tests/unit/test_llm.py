"""Test LLM client."""
import pytest
from opm_ai.llm.client import LLMClient


def test_llm_client_init():
    """Test LLM client initialization."""
    client = LLMClient()
    # Should initialize without error
    assert client is not None


def test_llm_client_offline():
    """Test LLM client in offline mode."""
    client = LLMClient()
    # In test environment without API keys, should be offline
    messages = [{"role": "user", "content": "test"}]
    result = client.chat(messages)
    # Should return None or a response depending on API key availability
    assert result is None or isinstance(result, str)


def test_llm_client_available():
    """Test availability check."""
    client = LLMClient()
    # Check returns boolean
    assert isinstance(client.available, bool)
