"""
DeckStudio FastAPI application entry point.

Startup sequence:
  1. Load and validate settings (fail-fast on missing API keys)
  2. Validate the Presentation Architect Prompt is present
  3. Start the session cleanup background task (runs every hour)
  4. Register CORS middleware and API routers

Run directly:
    python -m backend.main

Or via uvicorn:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import get_settings
from backend.api.routes import deck, health, fetch_url
from backend.services.session_service import get_session_service

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle manager."""
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("DeckStudio backend starting on %s:%d", settings.app_host, settings.app_port)
    logger.info("Model: %s", settings.deepagents_model)
    logger.info("Environment: %s", settings.app_env)

    # Fail-fast: validate the Presentation Architect Prompt is loadable
    try:
        from backend.prompts import PRESENTATION_ARCHITECT_PROMPT

        logger.info(
            "Presentation Architect Prompt loaded: %d chars",
            len(PRESENTATION_ARCHITECT_PROMPT),
        )
    except FileNotFoundError as exc:
        logger.critical("STARTUP FAILED: %s", exc)
        raise

    # Start periodic session cleanup background task
    async def cleanup_loop() -> None:
        while True:
            await asyncio.sleep(3600)  # Every hour
            svc = get_session_service()
            count = await svc.cleanup_expired()
            if count:
                logger.info("Cleaned up %d expired sessions", count)

    cleanup_task = asyncio.create_task(cleanup_loop())
    logger.info("Session cleanup task started (TTL=%d min)", settings.session_ttl_minutes)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("DeckStudio backend shut down cleanly")


# ─────────────────────────────────────────────────────────────────────────────
# Application instance
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="DeckStudio API",
    description=(
        "AI-powered presentation deck generator powered by a DeepAgents pipeline "
        "with human-in-the-loop (HITL) checkpoints at every stage."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── CORS middleware ───────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router, prefix="/api")
app.include_router(deck.router, prefix="/api/deck", tags=["deck"])
app.include_router(fetch_url.router, prefix="/api", tags=["deck"])


# ─────────────────────────────────────────────────────────────────────────────
# Direct entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level=settings.app_log_level,
    )
