"""Health check route — also reports whether the LLM API key is pre-configured."""
from datetime import datetime
from fastapi import APIRouter
from backend.config.settings import get_settings

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check() -> dict:
    """Return service health and API key configuration status.

    The frontend uses `api_key_configured` to decide whether to
    prompt the user for their Anthropic API key.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "deckstudio-backend",
        "timestamp": datetime.utcnow().isoformat(),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.anthropic_model if settings.llm_provider == "anthropic" else settings.openai_model,
        "api_key_configured": settings.api_key_configured,
    }
