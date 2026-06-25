"""
LLM provider configurations for OPM-AI.
Supports Groq (free) and NVIDIA NIM (free, Nemotron-Ultra-253B).
Both use the OpenAI-compatible API surface.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key_env: str
    default_model: str
    models: List[str]
    label: str  # display label
    badge: str  # emoji badge


PROVIDERS: dict[str, ProviderConfig] = {
    "groq": ProviderConfig(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        default_model="llama-3.3-70b-versatile",
        models=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ],
        label="Groq",
        badge="⚡",
    ),
    "nvidia": ProviderConfig(
        name="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key_env="NVIDIA_API_KEY",
        default_model="nvidia/llama-3.1-nemotron-ultra-253b-v1",
        models=[
            "nvidia/llama-3.1-nemotron-ultra-253b-v1",
            "nvidia/nemotron-4-340b-instruct",
            "meta/llama-3.1-70b-instruct",
            "mistralai/mistral-large-2-instruct",
        ],
        label="NVIDIA NIM",
        badge="🔥",
    ),
}


def get_provider(name: str) -> ProviderConfig:
    """Return a ProviderConfig by name. Raises KeyError on unknown provider."""
    if name not in PROVIDERS:
        raise KeyError(f"Unknown provider '{name}'. Valid: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]
