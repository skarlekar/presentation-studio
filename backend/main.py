"""
DeckStudio — FastAPI application entry point.

Startup sequence:
1. Validate Presentation Architect Prompt file exists (fail-fast)
2. Start hourly session cleanup background task
3. Mount CORS middleware and API routers
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import get_settings
from backend.api.routes import deck, health
from backend.services.session_service import get_session_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # ── Startup ──────────────────────────────────────────────────────────────
    print(f"[DeckStudio] Starting on {settings.app_host}:{settings.app_port}")
    print(f"[DeckStudio] Environment: {settings.app_env}")
    print(f"[DeckStudio] Model: {settings.deepagents_model}")

    # Fail-fast: ensure the canonical Presentation Architect Prompt is present
    try:
        from backend.prompts import PRESENTATION_ARCHITECT_PROMPT
        print(
            f"[DeckStudio] Presentation Architect Prompt loaded "
            f"({len(PRESENTATION_ARCHITECT_PROMPT):,} chars)"
        )
    except FileNotFoundError as e:
        # This will prevent the app from starting — by design
        raise RuntimeError(
            "CRITICAL: Presentation Architect Prompt file is missing. "
            "The application cannot start without it. "
            f"Expected at: backend/prompts/presentation_architect.txt\n{e}"
        ) from e

    # Hourly session cleanup task
    async def _cleanup_loop() -> None:
        while True:
            await asyncio.sleep(3600)
            try:
                svc = get_session_service()
                count = await svc.cleanup_expired()
                if count:
                    print(f"[DeckStudio] Cleaned up {count} expired session(s)")
            except Exception as exc:
                print(f"[DeckStudio] Session cleanup error: {exc}")

    cleanup_task = asyncio.create_task(_cleanup_loop())
    print("[DeckStudio] Session cleanup task started (runs hourly)")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    print("[DeckStudio] Backend shut down cleanly")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="DeckStudio API",
    description=(
        "AI-powered executive presentation deck generator. "
        "Uses a 5-agent DeepAgents pipeline with human-in-the-loop checkpoints "
        "to produce McKinsey/BCG-style slide decks from context and source material."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(deck.router, prefix="/api/deck", tags=["deck"])


# ── Dev entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=(settings.app_env == "development"),
        log_level=settings.app_log_level,
    )
