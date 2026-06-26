"""
LLM provider configurations for OPM-AI.
Supports Groq (free) and NVIDIA NIM (free, Nemotron-3 Super 120B).
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
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3-32b",
        ],
        label="Groq",
        badge="⚡",
    ),
    "nvidia": ProviderConfig(
        name="nvidia",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key_env="NVIDIA_NIM_API",
        default_model="nvidia/nemotron-3-super-120b-a12b",
        models=[
            "nvidia/nemotron-3-super-120b-a12b",
            "nvidia/nemotron-3-ultra-550b-a55b",
            "nvidia/nemotron-3-nano-30b-a3b",
            "nvidia/llama-3.3-nemotron-super-49b-v1.5",
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
