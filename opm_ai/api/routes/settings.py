"""Settings route: runtime LLM provider/key overrides.

POST sets IN-MEMORY overrides on the module-level settings singleton
(pydantic-settings allows plain attribute assignment; validate_assignment
is off, so no re-validation surprises). Nothing is written to .env or any
file, and key material is never echoed back. A fresh LLMClient() reads the
singleton at construction time and chat.py constructs one per connection,
so changes take effect without a restart.
"""

from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from opm_ai.settings import settings

router = APIRouter()


class SettingsUpdateRequest(BaseModel):
    """Runtime settings override. Keys are optional; empty string clears a key."""
    model_config = ConfigDict(from_attributes=True)

    provider: Literal["groq", "openai", "nim", "offline"]
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    nvidia_nim_api_key: Optional[str] = None


class SettingsResponse(BaseModel):
    """Current settings state. Booleans only for keys - never key material."""
    model_config = ConfigDict(from_attributes=True)

    provider: str
    active_provider: str
    keys_configured: dict[str, bool]


def _current_state() -> SettingsResponse:
    return SettingsResponse(
        provider=settings.llm_provider,
        active_provider=settings.active_llm_client,
        keys_configured={
            "groq": bool(settings.groq_api_key),
            "openai": bool(settings.openai_api_key),
            "nim": bool(settings.nvidia_nim_api_key),
        },
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Return the selected provider, the resolved active provider, and
    which providers have a key configured."""
    return _current_state()


@router.post("/settings", response_model=SettingsResponse)
async def update_settings(request: SettingsUpdateRequest) -> SettingsResponse:
    """Apply an in-memory settings override for this process.

    Omitted key fields leave the existing key untouched; an empty string
    clears it. active_provider in the response stays "offline" when the
    selected provider has no key (same resolution as active_llm_client).
    """
    if request.groq_api_key is not None:
        settings.groq_api_key = request.groq_api_key or None
    if request.openai_api_key is not None:
        settings.openai_api_key = request.openai_api_key or None
    if request.nvidia_nim_api_key is not None:
        settings.nvidia_nim_api_key = request.nvidia_nim_api_key or None
    settings.llm_provider = request.provider
    return _current_state()
