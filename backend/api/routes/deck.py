"""
Deck API routes — all /api/deck/* endpoints.

Endpoints:
  POST   /api/deck/generate
  GET    /api/deck/{session_id}/status
  POST   /api/deck/{session_id}/checkpoint/{checkpoint_id}/approve
  POST   /api/deck/{session_id}/checkpoint/{checkpoint_id}/reject
  GET    /api/deck/{session_id}
  PUT    /api/deck/{session_id}/slide/{slide_id}
  POST   /api/deck/{session_id}/approve
  POST   /api/deck/{session_id}/export
  GET    /api/deck/{session_id}/history
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, UploadFile, File, Form
from fastapi.responses import JSONResponse

from backend.schemas.input import (
    DeckRequest, SlideUpdateRequest,
    CheckpointApproveRequest, CheckpointRejectRequest,
    GenerateResponse,
)
from backend.schemas.output import (
    PipelineStatus, SessionStatusResponse, DeckEnvelope,
    DeckEnvelope, CheckpointStatus,
)
from backend.services.session_service import get_session_service, Session
from backend.services.file_service import save_deck, list_versions
from backend.agents.orchestrator import get_orchestrator, format_deck_request_message
from backend.agents.quality_validator import validate_deck_data

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_to_response(session: Session) -> dict:
    """Convert a Session to a SessionStatusResponse-compatible dict."""
    cp = session.current_checkpoint()
    return {
        "session_id": session.session_id,
        "status": session.status,
        "current_stage": session.current_stage,
        "progress_pct": session.progress_pct(),
        "checkpoint": cp.model_dump() if cp else None,
        "error": session.error,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _extract_stage_from_state(state) -> str:
    """Extract the current stage name from a LangGraph state."""
    # The interrupted node is in state.next — DeepAgents uses "task" tool
    # The pending task name is embedded in the last message's tool_calls
    try:
        messages = state.values.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("name") == "task":
                        args = tc.get("args", {})
                        return args.get("agent", args.get("name", "unknown"))
    except Exception:
        pass
    return "unknown"


def _extract_pending_input(state) -> dict:
    """Extract the pending tool call input from a LangGraph interrupted state."""
    try:
        messages = state.values.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("name") == "task":
                        return tc.get("args", {})
    except Exception:
        pass
    return {}


def _extract_deck_from_result(result) -> Optional[DeckEnvelope]:
    """Extract the DeckEnvelope from a completed pipeline result."""
    try:
        # DeepAgents puts structured response in state["structured_response"]
        if isinstance(result, dict):
            sr = result.get("structured_response")
            if sr:
                if isinstance(sr, DeckEnvelope):
                    return sr
                return DeckEnvelope.model_validate(sr)

            # Fallback: try to parse from final message content
            messages = result.get("messages", [])
            for msg in reversed(messages):
                content = getattr(msg, "content", "")
                if content and isinstance(content, str):
                    try:
                        data = json.loads(content)
                        return DeckEnvelope.model_validate(data)
                    except Exception:
                        continue
    except Exception:
        pass
    return None


# ── Pipeline runner ───────────────────────────────────────────────────────────

async def run_pipeline(session_id: str, request_data: dict) -> None:
    """Execute the DeepAgents pipeline in a background task.

    Runs until the first HITL interrupt or completion, then updates session state.
    """
    config = {"configurable": {"thread_id": session_id}}
    orchestrator = get_orchestrator()
    session_svc = get_session_service()

    try:
        await session_svc.update_status(session_id, PipelineStatus.RUNNING)

        input_msg = format_deck_request_message(request_data)

        # Run pipeline (blocking — offloaded to thread pool)
        result = await asyncio.to_thread(
            orchestrator.invoke,
            {"messages": [{"role": "user", "content": input_msg}]},
            config,
        )

        # Check state after invoke
        state = orchestrator.get_state(config)

        if state.next:
            # Pipeline paused at HITL checkpoint
            stage = _extract_stage_from_state(state)
            pending_input = _extract_pending_input(state)
            preview = pending_input.get("input", pending_input)
            await session_svc.update_status(session_id, PipelineStatus.AWAITING_APPROVAL, current_stage=stage)
            await session_svc.add_checkpoint(session_id, stage, pending_input, preview=preview)
        else:
            # Pipeline completed
            deck = _extract_deck_from_result(result)
            if deck:
                await session_svc.set_deck(session_id, deck)
            else:
                await session_svc.update_status(
                    session_id, PipelineStatus.FAILED,
                    error="Pipeline completed but no deck was produced",
                )

    except Exception as e:
        await session_svc.update_status(
            session_id, PipelineStatus.FAILED, error=str(e)
        )


async def resume_pipeline(session_id: str, edits: Optional[dict] = None) -> None:
    """Resume the pipeline after a HITL checkpoint approval."""
    config = {"configurable": {"thread_id": session_id}}
    orchestrator = get_orchestrator()
    session_svc = get_session_service()

    try:
        await session_svc.update_status(session_id, PipelineStatus.RUNNING)

        # Resume with optional edits
        resume_input = edits if edits else None

        result = await asyncio.to_thread(
            orchestrator.invoke,
            resume_input,
            config,
        )

        state = orchestrator.get_state(config)

        if state.next:
            stage = _extract_stage_from_state(state)
            pending_input = _extract_pending_input(state)
            preview = pending_input.get("input", pending_input)
            await session_svc.update_status(session_id, PipelineStatus.AWAITING_APPROVAL, current_stage=stage)
            await session_svc.add_checkpoint(session_id, stage, pending_input, preview=preview)
        else:
            deck = _extract_deck_from_result(result)
            if deck:
                await session_svc.set_deck(session_id, deck)
            else:
                await session_svc.update_status(
                    session_id, PipelineStatus.FAILED,
                    error="Pipeline resumed but no deck was produced",
                )

    except Exception as e:
        await session_svc.update_status(
            session_id, PipelineStatus.FAILED, error=str(e)
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse, status_code=202)
async def generate_deck(
    request: DeckRequest,
    background_tasks: BackgroundTasks,
) -> GenerateResponse:
    """Start the DeepAgents pipeline for a new deck.

    Returns a session_id immediately. Poll /status to track progress.
    """
    session_svc = get_session_service()
    request_data = request.model_dump()
    session = await session_svc.create_session(request_data)
    background_tasks.add_task(run_pipeline, session.session_id, request_data)
    return GenerateResponse(session_id=session.session_id, status="processing")


@router.get("/{session_id}/status")
async def get_status(session_id: str) -> dict:
    """Get current pipeline status for a session.

    Returns status, current_stage, progress_pct, and checkpoint (if awaiting approval).
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return _session_to_response(session)


@router.post("/{session_id}/checkpoint/{checkpoint_id}/approve", status_code=200)
async def approve_checkpoint(
    session_id: str,
    checkpoint_id: str,
    body: CheckpointApproveRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Approve a HITL checkpoint and resume the pipeline.

    Optionally include edits to modify the agent's output before resuming.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if session.status != PipelineStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Session is {session.status}, not awaiting_approval",
        )

    cp = await session_svc.resolve_checkpoint(
        session_id, checkpoint_id, "approved", edits=body.edits
    )
    if not cp:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")

    background_tasks.add_task(resume_pipeline, session_id, body.edits)
    return {"status": "advancing", "checkpoint_id": checkpoint_id}


@router.post("/{session_id}/checkpoint/{checkpoint_id}/reject", status_code=200)
async def reject_checkpoint(
    session_id: str,
    checkpoint_id: str,
    body: CheckpointRejectRequest,
) -> dict:
    """Reject a HITL checkpoint and halt the pipeline.

    The session is marked as REJECTED. A new session must be started to retry.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if session.status != PipelineStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Session is {session.status}, not awaiting_approval",
        )

    cp = await session_svc.resolve_checkpoint(session_id, checkpoint_id, "rejected")
    if not cp:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")

    await session_svc.update_status(
        session_id, PipelineStatus.REJECTED,
        error=f"Rejected at {session.current_stage}: {body.feedback}",
    )
    return {"status": "rejected", "feedback": body.feedback}


@router.get("/{session_id}")
async def get_deck(session_id: str, response: Response) -> dict:
    """Get the completed deck for a session.

    Returns 202 if pipeline is still processing, 200 with deck if complete.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if session.status != PipelineStatus.COMPLETED:
        response.status_code = 202
        return {"status": session.status, "message": "Deck not yet complete"}

    if not session.deck:
        raise HTTPException(status_code=500, detail="Session completed but no deck found")

    return session.deck.model_dump()


@router.put("/{session_id}/slide/{slide_id}")
async def update_slide(
    session_id: str,
    slide_id: str,
    body: SlideUpdateRequest,
) -> dict:
    """Update a single slide in the deck and re-validate it.

    Returns the updated slide and validation results.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if not session.deck:
        raise HTTPException(status_code=409, detail="No deck available to edit")

    # Find and update the slide
    deck = session.deck.deck
    all_slides = deck.slides + deck.appendix.slides
    target = next((s for s in all_slides if s.slide_id == slide_id), None)

    if not target:
        raise HTTPException(status_code=404, detail=f"Slide {slide_id} not found")

    # Apply updates
    update_data = body.model_dump(exclude_unset=True, exclude={"slide_id"})
    for key, value in update_data.items():
        if value is not None:
            setattr(target, key, value)

    # Re-validate the updated deck
    deck_json = session.deck.model_dump_json()
    report = validate_deck_data(deck_json)

    return {
        "slide": target.model_dump(),
        "validation": report.model_dump(),
    }


@router.post("/{session_id}/approve", status_code=200)
async def approve_deck(session_id: str) -> dict:
    """Mark the completed deck as human-approved and ready for export."""
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if session.status != PipelineStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Session is {session.status} — can only approve completed decks",
        )

    return {"status": "approved", "export_ready": True, "session_id": session_id}


@router.post("/{session_id}/export", status_code=200)
async def export_deck(session_id: str) -> dict:
    """Export the approved deck as a versioned JSON file.

    Returns filename, filepath, version, and saved_at timestamp.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if not session.deck:
        raise HTTPException(status_code=409, detail="No completed deck to export")

    result = await save_deck(session_id, session.deck)
    return result


@router.get("/{session_id}/history", status_code=200)
async def get_history(session_id: str) -> dict:
    """List all exported versions for a session's deck."""
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    title_slug = None
    if session.deck and session.deck.deck.title:
        title_slug = session.deck.deck.title

    versions = await list_versions(session_id, title_slug=title_slug)
    return {"versions": versions, "session_id": session_id}
