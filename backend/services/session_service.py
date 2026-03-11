"""
Session service — manages pipeline session state.

In-memory storage with asyncio Lock for thread safety.
Sessions are keyed by session_id (UUID).
Expired sessions are cleaned up periodically by the background task in main.py.

NOTE: In-memory storage is suitable for single-worker development only.
For production, migrate to SQLite or PostgreSQL backed storage.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from backend.config.settings import get_settings
from backend.schemas.output import (
    Checkpoint,
    CheckpointStatus,
    DeckEnvelope,
    PipelineStatus,
)

settings = get_settings()

# Maps pipeline stage name → (human-readable label, 1-based stage index)
STAGE_LABELS: dict[str, tuple[str, int]] = {
    "insight_extractor": ("Confirm Core Insights", 1),
    "deck_architect": ("Confirm Deck Outline", 2),
    "slide_generator": ("Review Generated Slides", 3),
    "appendix_builder": ("Confirm Appendix Content", 4),
    "quality_validator": ("Quality Validation", 5),
}

# Maps pipeline stage → progress percentage (0-100)
STAGE_PROGRESS: dict[str, int] = {
    "insight_extractor": 20,
    "deck_architect": 40,
    "slide_generator": 60,
    "appendix_builder": 80,
    "quality_validator": 95,
}


@dataclass
class Session:
    """In-memory representation of a deck generation session."""

    session_id: str
    status: PipelineStatus = PipelineStatus.PENDING
    current_stage: Optional[str] = None
    checkpoints: list = field(default_factory=list)
    deck: Optional[DeckEnvelope] = None
    error: Optional[str] = None
    quality_retry_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    request_data: Optional[dict] = None
    agent_steps: list = field(default_factory=list)
    # Each entry: {name, status, started_at, completed_at, output_summary, output_full}

    def progress_pct(self) -> int:
        """Return estimated pipeline completion percentage (0-100)."""
        if self.status in (PipelineStatus.COMPLETED, PipelineStatus.COMPLETE):
            return 100
        if self.status == PipelineStatus.FAILED:
            return 0
        return STAGE_PROGRESS.get(self.current_stage or "", 0)

    def current_checkpoint(self) -> Optional[Checkpoint]:
        """Return the first PENDING checkpoint, or None."""
        for cp in reversed(self.checkpoints):
            if cp.status == CheckpointStatus.PENDING:
                return cp
        return None


class SessionService:
    """Thread-safe in-memory session store for pipeline sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, request_data: dict) -> Session:
        """Create and store a new session, returning the Session object."""
        async with self._lock:
            session_id = str(uuid.uuid4())
            session = Session(
                session_id=session_id,
                status=PipelineStatus.PENDING,
                request_data=request_data,
            )
            self._sessions[session_id] = session
            return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Return the session by ID, or None if not found."""
        return self._sessions.get(session_id)

    async def update_status(
        self,
        session_id: str,
        status: PipelineStatus,
        current_stage: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update session status, optionally setting current_stage and error."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = status
                if current_stage is not None:
                    session.current_stage = current_stage
                if error is not None:
                    session.error = error
                session.updated_at = datetime.utcnow()

    async def add_checkpoint(
        self,
        session_id: str,
        stage: str,
        pending_input: dict,
        preview: Optional[dict] = None,
    ) -> Checkpoint:
        """Create a new PENDING checkpoint for the given stage.

        Sets session status to AWAITING_APPROVAL.
        Raises ValueError if session not found.
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise ValueError(f"Session {session_id!r} not found")

            label, stage_index = STAGE_LABELS.get(stage, (stage, 0))
            now = datetime.utcnow().isoformat()

            checkpoint = Checkpoint(
                checkpoint_id=str(uuid.uuid4()),
                session_id=session_id,
                stage=stage,
                stage_index=stage_index,
                label=label,
                status=CheckpointStatus.PENDING,
                pending_input=pending_input,
                preview=preview,
                payload=pending_input,  # also populate payload for compatibility
                created_at=now,
            )
            session.checkpoints.append(checkpoint)
            session.status = PipelineStatus.AWAITING_APPROVAL
            session.current_stage = stage
            session.updated_at = datetime.utcnow()
            return checkpoint

    async def resolve_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
        resolution: str,
        edits: Optional[dict] = None,
    ) -> Optional[Checkpoint]:
        """Approve or reject a checkpoint by ID.

        Args:
            session_id: Session identifier.
            checkpoint_id: Checkpoint to resolve.
            resolution: 'approved' or 'rejected'.
            edits: Optional edits submitted with the resolution.

        Returns:
            Updated Checkpoint, or None if not found.
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            for cp in session.checkpoints:
                if cp.checkpoint_id == checkpoint_id:
                    cp.status = (
                        CheckpointStatus.APPROVED
                        if resolution == "approved"
                        else CheckpointStatus.REJECTED
                    )
                    cp.resolution = resolution
                    cp.resolved_at = datetime.utcnow().isoformat()
                    cp.edits = edits
                    session.updated_at = datetime.utcnow()
                    return cp
            return None

    async def set_deck(self, session_id: str, deck: DeckEnvelope) -> None:
        """Store the completed deck and set status to COMPLETED."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.deck = deck
                session.status = PipelineStatus.COMPLETED
                session.updated_at = datetime.utcnow()

    async def increment_quality_retry(self, session_id: str) -> int:
        """Increment and return the quality retry counter for the session."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.quality_retry_count += 1
                session.updated_at = datetime.utcnow()
                return session.quality_retry_count
            return 0

    async def start_agent_step(self, session_id: str, agent_name: str) -> None:
        """Record the start of a subagent step."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            # Don't add duplicate if already running/completed
            for step in session.agent_steps:
                if step["name"] == agent_name and step["status"] in ("running", "completed"):
                    return
            session.agent_steps.append({
                "name": agent_name,
                "status": "running",
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": None,
                "output_summary": None,
                "output_full": None,
            })
            session.updated_at = datetime.utcnow()

    async def complete_agent_step(
        self, session_id: str, agent_name: str, output_full: Optional[str] = None
    ) -> None:
        """Mark a subagent step as completed."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            for step in session.agent_steps:
                if step["name"] == agent_name and step["status"] == "running":
                    step["status"] = "completed"
                    step["completed_at"] = datetime.utcnow().isoformat()
                    if output_full:
                        # Store full output, truncate summary
                        step["output_full"] = output_full
                        step["output_summary"] = (output_full[:200] + "…") if len(output_full) > 200 else output_full
                    break
            session.updated_at = datetime.utcnow()

    async def fail_agent_step(
        self, session_id: str, agent_name: str, error: Optional[str] = None
    ) -> None:
        """Mark a subagent step as failed."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            for step in session.agent_steps:
                if step["name"] == agent_name and step["status"] == "running":
                    step["status"] = "failed"
                    step["completed_at"] = datetime.utcnow().isoformat()
                    if error:
                        step["output_full"] = error
                        step["output_summary"] = error[:200]
                    break
            session.updated_at = datetime.utcnow()

    async def cleanup_expired(self) -> int:
        """Remove sessions older than SESSION_TTL_MINUTES.

        Returns:
            Number of sessions removed.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=settings.session_ttl_minutes)
        async with self._lock:
            expired = [
                sid
                for sid, s in self._sessions.items()
                if s.created_at < cutoff
            ]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)

    def get_all_sessions(self) -> dict[str, Session]:
        """Return a snapshot of all sessions (not locked — for read-only use)."""
        return dict(self._sessions)


# Module-level singleton
_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """Return the cached SessionService singleton."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
