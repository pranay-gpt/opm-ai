"""Application settings using pydantic-settings."""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OPM Flow
    flow_path: Path = Field(default=Path("/usr/bin/flow"), validation_alias="OPM_FLOW_BINARY")

    # ResInsight
    resinsight_grpc_port: int = Field(default=50051, validation_alias="RESINSIGHT_GRPC_PORT")
    resinsight_executable: Path = Field(default=Path("/usr/bin/ResInsight"), validation_alias="RESINSIGHT_EXECUTABLE")

    # LLM Providers
    groq_api_key: Optional[str] = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", validation_alias="GROQ_MODEL")

    # NVIDIA NIM (OpenAI-compatible)
    nvidia_nim_api_key: Optional[str] = Field(default=None, validation_alias="NVIDIA_NIM_API")

    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, validation_alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o", validation_alias="OPENAI_MODEL")

    # LLM provider selection: "groq" | "openai" | "offline"
    llm_provider: str = Field(default="offline", validation_alias="LLM_PROVIDER")

    # Tavily API for web search
    tavily_api_key: Optional[str] = Field(default=None, validation_alias="TAVILY_API")

    # API
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")

    # Frontend (for CORS)
    frontend_url: str = Field(default="http://localhost:5173", validation_alias="FRONTEND_URL")

    # Reference decks
    fixtures_path: Path = Field(default=Path("tests/fixtures"), validation_alias="FIXTURES_PATH")

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # Offline mode (no API keys)
    @property
    def offline_mode(self) -> bool:
        """Return True if running in offline mode (no API keys)."""
        return self.llm_provider == "offline" or (
            not self.groq_api_key and not self.openai_api_key and not self.nvidia_nim_api_key
        )

    @property
    def active_llm_client(self) -> str:
        """Return the active LLM provider name."""
        if self.groq_api_key and self.llm_provider in ("groq", "auto"):
            return "groq"
        if self.openai_api_key and self.llm_provider in ("openai", "auto"):
            return "openai"
        return "offline"


# Global settings instance
settings = Settings()