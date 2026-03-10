"""
DeckStudio backend configuration.

All settings are loaded from environment variables (or a .env file).
Use pydantic-settings for validation and type coercion.
Never import this module at the top level of tests — always use the
``get_settings()`` cached accessor so tests can override via monkeypatch.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Precedence (highest → lowest):
        1. Real environment variables
        2. .env file (if present)
        3. Default values defined here
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # silently ignore unknown env vars
    )

    # ─────────────────────────────────────────
    # APPLICATION
    # ─────────────────────────────────────────

    app_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment. Controls debug mode, log verbosity, etc.",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Python logging level for the entire application.",
    )

    app_title: str = Field(
        default="DeckStudio API",
        description="Title shown in the OpenAPI docs (/docs).",
    )

    app_version: str = Field(
        default="0.1.0",
        description="Semantic version string for the API.",
    )

    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description=(
            "Comma-separated list of allowed CORS origins. "
            "Accepts a JSON-encoded list or a bare comma-separated string."
        ),
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> list[str]:
        """Accept either a list or a comma-separated string from the env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    # ─────────────────────────────────────────
    # SERVER
    # ─────────────────────────────────────────

    host: str = Field(
        default="0.0.0.0",
        description="Host interface for uvicorn to bind.",
    )

    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="TCP port for uvicorn.",
    )

    workers: int = Field(
        default=1,
        ge=1,
        description=(
            "Number of uvicorn worker processes. "
            "Set >1 in production only; not compatible with in-memory session store."
        ),
    )

    # ─────────────────────────────────────────
    # LLM PROVIDERS
    # ─────────────────────────────────────────

    llm_provider: Literal["anthropic", "openai"] = Field(
        default="anthropic",
        description="Primary LLM provider. Determines which API key / model is used.",
    )

    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key. Required when llm_provider='anthropic'.",
    )

    anthropic_model: str = Field(
        default="claude-sonnet-4-5",
        description="Anthropic model identifier passed to the ChatAnthropic client.",
    )

    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key. Required when llm_provider='openai'.",
    )

    openai_model: str = Field(
        default="gpt-4o",
        description="OpenAI model identifier passed to the ChatOpenAI client.",
    )

    llm_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description=(
            "Sampling temperature for LLM calls. "
            "Lower = more deterministic; higher = more creative."
        ),
    )

    llm_max_tokens: int = Field(
        default=8192,
        ge=256,
        description="Maximum tokens the LLM may generate in a single response.",
    )

    llm_timeout_seconds: int = Field(
        default=120,
        ge=10,
        description="HTTP timeout in seconds for LLM API calls.",
    )

    @model_validator(mode="after")
    def _validate_api_keys(self) -> "Settings":
        """API keys are optional at startup — can be supplied per-request from the frontend.

        This allows the app to start without pre-configured keys; the frontend
        will detect the missing key via the /api/health endpoint and prompt the user.
        """
        # Keys are intentionally optional — validated at request time if missing
        return self

    @property
    def api_key_configured(self) -> bool:
        """True if the active provider's API key is available in environment."""
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        return bool(self.openai_api_key)

    # ─────────────────────────────────────────
    # AGENT PIPELINE
    # ─────────────────────────────────────────

    langgraph_max_steps: int = Field(
        default=50,
        ge=1,
        description="Maximum recursion depth for LangGraph agent graphs.",
    )

    checkpoint_enabled: bool = Field(
        default=True,
        description=(
            "Enable human-in-the-loop checkpoints. "
            "When False the pipeline runs fully autonomously."
        ),
    )

    checkpoint_stages: list[str] = Field(
        default=["outline", "review"],
        description=(
            "Pipeline stages where human approval is required. "
            "Valid values: outline | slides | review | all"
        ),
    )

    @field_validator("checkpoint_stages", mode="before")
    @classmethod
    def _parse_checkpoint_stages(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v  # type: ignore[return-value]

    session_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        description="Time-to-live for agent sessions in seconds.",
    )

    # ─────────────────────────────────────────
    # FILE PROCESSING
    # ─────────────────────────────────────────

    max_upload_size_mb: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum allowed file upload size in megabytes.",
    )

    allowed_mime_types: list[str] = Field(
        default=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
        ],
        description="MIME types accepted for source material uploads.",
    )

    @field_validator("allowed_mime_types", mode="before")
    @classmethod
    def _parse_mime_types(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v  # type: ignore[return-value]

    upload_temp_dir: str | None = Field(
        default=None,
        description=(
            "Temporary directory for uploaded files. "
            "Defaults to the system temp directory when None."
        ),
    )

    # ─────────────────────────────────────────
    # STORAGE
    # ─────────────────────────────────────────

    storage_backend: Literal["memory", "sqlite", "postgres"] = Field(
        default="memory",
        description=(
            "Session / deck storage backend. "
            "'memory' is suitable only for single-worker development. "
            "Use 'sqlite' for local persistence or 'postgres' for production."
        ),
    )

    sqlite_path: str = Field(
        default="data/deckstudio.db",
        description="Path to SQLite database file. Only used when storage_backend='sqlite'.",
    )

    database_url: str | None = Field(
        default=None,
        description=(
            "PostgreSQL async DSN. "
            "Example: postgresql+asyncpg://user:password@localhost:5432/deckstudio. "
            "Only used when storage_backend='postgres'."
        ),
    )

    # ─────────────────────────────────────────
    # SECURITY
    # ─────────────────────────────────────────

    secret_key: str = Field(
        default="change-me-in-production",
        description=(
            "Secret key for signing tokens. "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        ),
    )

    api_key: str | None = Field(
        default=None,
        description=(
            "If set, all API routes require this key in the X-API-Key header. "
            "Leave unset (None) to disable API key auth in development."
        ),
    )

    # ─────────────────────────────────────────
    # OBSERVABILITY
    # ─────────────────────────────────────────

    langsmith_tracing: bool = Field(
        default=False,
        description="Enable LangSmith distributed tracing for LangGraph pipelines.",
    )

    langsmith_api_key: str | None = Field(
        default=None,
        description="LangSmith API key. Required when langsmith_tracing=True.",
    )

    langsmith_project: str = Field(
        default="deckstudio",
        description="LangSmith project name for trace grouping.",
    )

    json_logs: bool = Field(
        default=False,
        description=(
            "Emit structured JSON log lines instead of human-readable text. "
            "Enable in production for log aggregation pipelines."
        ),
    )

    # ─────────────────────────────────────────
    # DERIVED PROPERTIES
    # ─────────────────────────────────────────

    # ─────────────────────────────────────────
    # PIPELINE / DEEPAGENTS
    # ─────────────────────────────────────────

    deepagents_checkpoint_db: str = Field(
        default="data/checkpoints/pipeline.db",
        description="Path to SQLite DB used by LangGraph SqliteSaver for pipeline checkpoints.",
    )

    export_dir: str = Field(
        default="data/exports",
        description="Directory where exported deck JSON files are saved.",
    )

    # ─────────────────────────────────────────
    # DERIVED PROPERTIES
    # ─────────────────────────────────────────

    @property
    def is_development(self) -> bool:
        """True when running in the development environment."""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """True when running in the production environment."""
        return self.app_env == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        """Maximum upload size in bytes derived from max_upload_size_mb."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def active_model(self) -> str:
        """Return the model name for the active LLM provider."""
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        return self.openai_model

    @property
    def active_api_key(self) -> str | None:
        """Return the API key for the active LLM provider."""
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        return self.openai_api_key

    # ── Compatibility aliases ─────────────────────────────────────────────

    @property
    def deepagents_model(self) -> str:
        """Alias for active_model — used by orchestrator."""
        return self.active_model

    @property
    def app_host(self) -> str:
        """Alias for host — used by main.py."""
        return self.host

    @property
    def app_port(self) -> int:
        """Alias for port — used by main.py."""
        return self.port

    @property
    def app_env_name(self) -> str:
        """Alias for app_env — used by main.py."""
        return self.app_env

    @property
    def app_log_level(self) -> str:
        """Return log level in lowercase for uvicorn — used by main.py."""
        return self.log_level.lower()

    @property
    def cors_origins_list(self) -> list[str]:
        """Alias for cors_origins — used by main.py."""
        return self.cors_origins

    @property
    def session_ttl_minutes(self) -> int:
        """Session TTL in minutes derived from session_ttl_seconds."""
        return self.session_ttl_seconds // 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application Settings singleton.

    In tests, call ``get_settings.cache_clear()`` after monkeypatching env vars
    to force re-instantiation with the patched values.
    """
    return Settings()
