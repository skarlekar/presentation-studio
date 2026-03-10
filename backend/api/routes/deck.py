"""
Deck generation API routes.

Endpoints:
  POST   /api/deck/generate                                  Start deck generation
  GET    /api/deck/{session_id}/status                       Poll pipeline status
  POST   /api/deck/{session_id}/checkpoint/{id}/approve      Approve HITL checkpoint
  POST   /api/deck/{session_id}/checkpoint/{id}/reject       Reject HITL checkpoint
  GET    /api/deck/{session_id}                              Fetch completed deck (202 while running)
  PUT    /api/deck/{session_id}/slide/{slide_id}             Update a single slide
  POST   /api/deck/{session_id}/approve                      Mark deck as approved
  POST   /api/deck/{session_id}/export                       Export deck to versioned JSON file
  GET    /api/deck/{session_id}/history                      List exported versions
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.agents.orchestrator import get_orchestrator
from backend.config.settings import get_settings
from backend.schemas.input import (
    CheckpointApproveRequest,
    CheckpointRejectRequest,
    DeckRequest,
    GenerateResponse,
    SlideUpdateRequest,
)
from backend.schemas.output import (
    CheckpointStatus,
    DeckEnvelope,
    PipelineStatus,
    SessionStatusResponse,
)
from backend.services.file_service import list_versions, save_deck
from backend.services.session_service import Session, get_session_service
from backend.services.source_material_service import SourceMaterialError, extract_text_from_file

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models specific to this router
# ─────────────────────────────────────────────────────────────────────────────


class CheckpointApproveBody(BaseModel):
    """Body for checkpoint approval."""
    comment: Optional[str] = Field(default=None, description="Optional reviewer comment.")
    edits: Optional[dict[str, Any]] = Field(default=None, description="Optional edits to apply.")


class CheckpointRejectBody(BaseModel):
    """Body for checkpoint rejection."""
    feedback: str = Field(..., min_length=10, description="Revision instructions for the agent.")
    slide_ids: Optional[list[str]] = Field(default=None, description="Slide IDs the feedback applies to.")


class SlideUpdateBody(BaseModel):
    """Body for updating a single slide field."""
    field: str = Field(..., description="Slide field to update (e.g. 'title', 'metaphor').")
    value: Any = Field(..., description="New value for the field.")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _session_not_found(session_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Session '{session_id}' not found.",
    )


def _conflict(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    )


def _session_to_status_response(session: Session) -> SessionStatusResponse:
    """Convert a Session dataclass to a SessionStatusResponse schema."""
    slides_generated = 0
    total_slides = 0

    if session.deck and session.deck.deck:
        slides_generated = len(session.deck.deck.slides)
        total_slides = session.deck.deck.total_slides

    return SessionStatusResponse(
        session_id=session.session_id,
        status=session.status,
        current_stage=session.current_stage,
        slides_generated=slides_generated,
        total_slides=total_slides,
        active_checkpoint=session.current_checkpoint(),
        error=session.error,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
    )


def format_deck_request_message(request: DeckRequest) -> str:
    """Format the DeckRequest into a structured message for the orchestrator."""
    parts = [
        "## DECK GENERATION REQUEST",
        "",
        f"**DECK_TYPE:** {request.deck_type.value}",
        f"**AUDIENCE:** {request.audience}",
        f"**TONE:** {request.tone}",
        f"**DECISION_INFORM_ASK:** {request.decision_inform_ask.value}",
        f"**NUMBER_OF_SLIDES:** {request.number_of_slides}",
    ]

    if request.context:
        parts += ["", "**CONTEXT:**", request.context]

    if request.source_material:
        parts += ["", "**SOURCE_MATERIAL:**", request.source_material]

    if request.must_include_sections:
        sections_str = "\n".join(f"- {s}" for s in request.must_include_sections)
        parts += ["", "**MUST_INCLUDE_SECTIONS:**", sections_str]

    if request.top_messages:
        msgs_str = "\n".join(f"- {m}" for m in request.top_messages)
        parts += ["", "**TOP_MESSAGES:**", msgs_str]

    if request.known_metrics:
        metrics_str = "\n".join(f"- {m}" for m in request.known_metrics)
        parts += ["", "**KNOWN_METRICS:**", metrics_str]

    if request.brand_style_guide:
        parts += ["", "**BRAND_STYLE_GUIDE:**", request.brand_style_guide]

    return "\n".join(parts)


def _extract_stage_from_state(state) -> str:
    """Extract the current pipeline stage name from a LangGraph state object."""
    try:
        # LangGraph interrupt state stores the next node name in state.next
        if hasattr(state, "next") and state.next:
            return str(state.next[0])
    except (IndexError, AttributeError, TypeError):
        pass
    return "unknown"


def _extract_pending_input(state) -> dict:
    """Extract the pending input payload from a LangGraph interrupted state."""
    try:
        # The interrupted task's input is stored in state.tasks[0].interrupts
        tasks = getattr(state, "tasks", [])
        if tasks:
            task = tasks[0]
            interrupts = getattr(task, "interrupts", [])
            if interrupts:
                interrupt = interrupts[0]
                val = getattr(interrupt, "value", None)
                if isinstance(val, dict):
                    return val
                elif val is not None:
                    return {"value": str(val)}
    except (AttributeError, IndexError, TypeError):
        pass
    return {}


def _extract_json_from_content(content: str) -> Optional[dict]:
    """Extract JSON from a string that may be a raw JSON object or a markdown code block.

    Handles:
    - Raw JSON: ``{"key": ...}``
    - Fenced code block: ```json\\n{...}\\n```
    - Fenced code block without language tag: ```\\n{...}\\n```
    """
    import re
    text = content.strip()

    # Try fenced code blocks first (```json ... ``` or ``` ... ```)
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try the whole string as JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Last resort: find the first { ... } block spanning the full content
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            data = json.loads(brace_match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return None


def _extract_deck_from_result(result: Any) -> Optional[DeckEnvelope]:
    """Extract a DeckEnvelope from the orchestrator result.

    Handles three cases:
    1. result IS already a DeckEnvelope (structured output mode)
    2. result is a dict with a "messages" key — parse last message content as JSON
       (plain output mode where the LLM emits a JSON code block)
    3. result is a dict that validates directly as DeckEnvelope
    """
    if isinstance(result, DeckEnvelope):
        return result

    if isinstance(result, dict):
        # Walk messages from last to first looking for a parseable DeckEnvelope
        messages = result.get("messages", [])
        for msg in reversed(messages):
            content = getattr(msg, "content", None) or (
                msg.get("content") if isinstance(msg, dict) else None
            )
            if not content or not isinstance(content, str):
                continue
            data = _extract_json_from_content(content)
            if data:
                try:
                    return DeckEnvelope.model_validate(data)
                except Exception:
                    pass  # Not a DeckEnvelope — keep scanning

        # Try direct dict validation as last resort
        try:
            return DeckEnvelope.model_validate(result)
        except Exception:
            pass

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Background pipeline runner
# ─────────────────────────────────────────────────────────────────────────────


async def run_pipeline(session_id: str, request: DeckRequest) -> None:
    """Run the DeepAgents pipeline in the background.

    This coroutine is invoked via FastAPI BackgroundTasks. It drives the
    orchestrator forward, creating HITL checkpoints when the graph interrupts,
    and setting the final deck on completion.

    Args:
        session_id: The session to update throughout the run.
        request: The validated DeckRequest driving this pipeline run.
    """
    config = {"configurable": {"thread_id": session_id}}
    # Pass user-supplied API key (used when ANTHROPIC_API_KEY not in env)
    orchestrator = get_orchestrator(api_key=request.api_key)
    session_svc = get_session_service()

    try:
        await session_svc.update_status(session_id, PipelineStatus.RUNNING)
        logger.info("Pipeline started for session %s", session_id)

        input_msg = format_deck_request_message(request)

        # Run the orchestrator synchronously in a thread to avoid blocking the event loop
        result = await asyncio.to_thread(
            orchestrator.invoke,
            {"messages": [{"role": "user", "content": input_msg}]},
            config,
        )

        # Check whether the pipeline paused at a HITL checkpoint
        state = await asyncio.to_thread(orchestrator.get_state, config)

        if getattr(state, "next", None):
            # Pipeline interrupted — surface a HITL checkpoint
            stage = _extract_stage_from_state(state)
            pending_input = _extract_pending_input(state)
            await session_svc.add_checkpoint(session_id, stage, pending_input)
            logger.info(
                "Pipeline paused at HITL checkpoint (stage=%s) for session %s",
                stage,
                session_id,
            )
        else:
            # Pipeline completed — extract and store the deck
            deck = _extract_deck_from_result(result)
            if deck:
                await session_svc.set_deck(session_id, deck)
                logger.info("Pipeline completed for session %s", session_id)
            else:
                await session_svc.update_status(
                    session_id,
                    PipelineStatus.FAILED,
                    error="Pipeline completed but produced no deck output.",
                )
                logger.error("Pipeline returned no deck for session %s", session_id)

    except Exception as exc:
        logger.exception("Pipeline error for session %s: %s", session_id, exc)
        await session_svc.update_status(
            session_id,
            PipelineStatus.FAILED,
            error=str(exc),
        )


async def resume_pipeline(session_id: str) -> None:
    """Resume a pipeline after a HITL checkpoint is approved.

    Calls orchestrator.invoke with None input (resumes from checkpoint)
    and processes the result the same way as run_pipeline.

    Args:
        session_id: The session to resume.
    """
    config = {"configurable": {"thread_id": session_id}}
    session_svc = get_session_service()

    # Retrieve the api_key from the original request (stored in session.request_data)
    # so the resumed pipeline uses the same LLM credentials as the initial run.
    session = await session_svc.get_session(session_id)
    stored_api_key = (
        (session.request_data or {}).get("api_key")
        if session else None
    )
    orchestrator = get_orchestrator(api_key=stored_api_key)

    try:
        await session_svc.update_status(session_id, PipelineStatus.RUNNING)
        logger.info("Resuming pipeline for session %s", session_id)

        # Resume from the last checkpoint by passing None
        result = await asyncio.to_thread(
            orchestrator.invoke,
            None,
            config,
        )

        state = await asyncio.to_thread(orchestrator.get_state, config)

        if getattr(state, "next", None):
            stage = _extract_stage_from_state(state)
            pending_input = _extract_pending_input(state)
            await session_svc.add_checkpoint(session_id, stage, pending_input)
            logger.info(
                "Pipeline paused at next checkpoint (stage=%s) for session %s",
                stage,
                session_id,
            )
        else:
            deck = _extract_deck_from_result(result)
            if deck:
                await session_svc.set_deck(session_id, deck)
                logger.info("Pipeline completed for session %s", session_id)
            else:
                await session_svc.update_status(
                    session_id,
                    PipelineStatus.FAILED,
                    error="Pipeline resumed but produced no deck output.",
                )

    except Exception as exc:
        logger.exception("Pipeline resume error for session %s: %s", session_id, exc)
        await session_svc.update_status(
            session_id,
            PipelineStatus.FAILED,
            error=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerateResponse,
    summary="Start deck generation",
)
async def generate_deck(
    request: DeckRequest,
    background_tasks: BackgroundTasks,
) -> GenerateResponse:
    """Accept a DeckRequest and start the DeepAgents pipeline in the background.

    Returns 202 Accepted immediately with a session_id and stream_url.
    Poll GET /api/deck/{session_id}/status or approve/reject checkpoints as they arrive.
    """
    session_svc = get_session_service()
    session = await session_svc.create_session(request.model_dump())

    background_tasks.add_task(run_pipeline, session.session_id, request)

    return GenerateResponse(
        session_id=session.session_id,
        status="accepted",
        message=(
            f"Deck generation started. "
            f"Poll status at /api/deck/{session.session_id}/status."
        ),
        stream_url=f"/api/deck/{session.session_id}/status",
    )


@router.post(
    "/generate/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerateResponse,
    summary="Start deck generation with file upload",
)
async def generate_deck_with_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Source material file (PDF, DOCX, TXT, MD — max 10 MB)."),
    context: str = Body(..., description="Deck context / background."),
    number_of_slides: int = Body(..., ge=3, le=60),
    audience: str = Body(...),
    deck_type: str = Body(...),
    decision_inform_ask: str = Body(...),
    tone: str = Body(...),
) -> GenerateResponse:
    """Accept source material as a file upload and start the pipeline.

    The file is extracted to plain text before pipeline invocation.
    """
    from backend.schemas.input import DeckType, DecisionInformAsk

    file_content = await file.read()
    try:
        source_material = await extract_text_from_file(
            file_content,
            file.filename or "upload",
            file.content_type,
        )
    except SourceMaterialError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    try:
        deck_type_enum = DeckType(deck_type)
        dia_enum = DecisionInformAsk(decision_inform_ask)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    request = DeckRequest(
        context=context,
        source_material=source_material,
        number_of_slides=number_of_slides,
        audience=audience,
        deck_type=deck_type_enum,
        decision_inform_ask=dia_enum,
        tone=tone,
    )

    session_svc = get_session_service()
    session = await session_svc.create_session(request.model_dump())
    background_tasks.add_task(run_pipeline, session.session_id, request)

    return GenerateResponse(
        session_id=session.session_id,
        status="accepted",
        message=(
            f"Deck generation started with uploaded file '{file.filename}'. "
            f"Poll status at /api/deck/{session.session_id}/status."
        ),
        stream_url=f"/api/deck/{session.session_id}/status",
    )


@router.get(
    "/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Poll pipeline status",
)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    """Return the current pipeline status for a session.

    Includes the active HITL checkpoint (if any) so the client can render
    the approval UI.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)
    return _session_to_status_response(session)


@router.post(
    "/{session_id}/checkpoint/{checkpoint_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve a HITL checkpoint",
)
async def approve_checkpoint(
    session_id: str,
    checkpoint_id: str,
    body: CheckpointApproveBody,
    background_tasks: BackgroundTasks,
) -> dict:
    """Approve a pipeline checkpoint and resume execution.

    The pipeline continues in the background from the next stage.
    Returns 409 if the checkpoint is not in PENDING state.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)

    cp = session.current_checkpoint()
    if not cp or cp.checkpoint_id != checkpoint_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checkpoint '{checkpoint_id}' not found or not pending.",
        )
    if cp.status != CheckpointStatus.PENDING:
        raise _conflict(f"Checkpoint '{checkpoint_id}' is already {cp.status.value}.")

    resolved = await session_svc.resolve_checkpoint(
        session_id, checkpoint_id, "approved", edits=body.edits
    )
    if not resolved:
        raise _session_not_found(session_id)

    # Resume pipeline in background
    background_tasks.add_task(resume_pipeline, session_id)

    return {
        "session_id": session_id,
        "checkpoint_id": checkpoint_id,
        "status": "approved",
        "message": "Checkpoint approved. Pipeline resuming.",
    }


@router.post(
    "/{session_id}/checkpoint/{checkpoint_id}/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject a HITL checkpoint",
)
async def reject_checkpoint(
    session_id: str,
    checkpoint_id: str,
    body: CheckpointRejectBody,
) -> dict:
    """Reject a pipeline checkpoint and halt the pipeline.

    The session is marked FAILED with the rejection feedback stored.
    The client should start a new session incorporating the feedback.
    Returns 409 if the checkpoint is not in PENDING state.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)

    cp = session.current_checkpoint()
    if not cp or cp.checkpoint_id != checkpoint_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checkpoint '{checkpoint_id}' not found or not pending.",
        )
    if cp.status != CheckpointStatus.PENDING:
        raise _conflict(f"Checkpoint '{checkpoint_id}' is already {cp.status.value}.")

    await session_svc.resolve_checkpoint(session_id, checkpoint_id, "rejected")
    await session_svc.update_status(
        session_id,
        PipelineStatus.FAILED,
        error=f"Checkpoint rejected: {body.feedback}",
    )

    return {
        "session_id": session_id,
        "checkpoint_id": checkpoint_id,
        "status": "rejected",
        "message": "Checkpoint rejected. Pipeline halted. Start a new session with your feedback.",
        "feedback": body.feedback,
    }


@router.get(
    "/{session_id}",
    summary="Fetch the completed deck",
)
async def get_deck(session_id: str) -> JSONResponse:
    """Return the completed DeckEnvelope for a session.

    Returns 200 with the DeckEnvelope when status is COMPLETED.
    Returns 202 Accepted with a status summary while the pipeline is still running.
    Returns 404 for unknown sessions.
    Returns 400 when the session failed.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)

    if session.status in (PipelineStatus.COMPLETED, PipelineStatus.COMPLETE):
        if session.deck:
            return JSONResponse(
                content=json.loads(session.deck.model_dump_json()),
                status_code=status.HTTP_200_OK,
            )

    if session.status == PipelineStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session failed: {session.error or 'Unknown error'}",
        )

    # Still running or awaiting approval
    return JSONResponse(
        content={
            "session_id": session_id,
            "status": session.status.value,
            "progress_pct": session.progress_pct(),
            "current_stage": session.current_stage,
            "message": "Deck generation is in progress. Poll /status for updates.",
        },
        status_code=status.HTTP_202_ACCEPTED,
    )


@router.put(
    "/{session_id}/slide/{slide_id}",
    status_code=status.HTTP_200_OK,
    summary="Update a single slide",
)
async def update_slide(
    session_id: str,
    slide_id: str,
    body: SlideUpdateBody,
) -> dict:
    """Update a single field on a slide in the completed deck.

    Performs schema validation on the updated slide.
    Returns 404 if session or slide not found.
    Returns 409 if the session is not in COMPLETED state.
    Returns 422 if the field value fails schema validation.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)

    if session.status not in (PipelineStatus.COMPLETED, PipelineStatus.COMPLETE):
        raise _conflict(
            f"Slide updates require a COMPLETED session; current status is '{session.status.value}'."
        )

    if not session.deck or not session.deck.deck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No deck found in this session.",
        )

    deck = session.deck.deck

    # Find the slide in main slides or appendix
    target_slide = None
    all_slides = deck.slides + deck.appendix.slides
    for slide in all_slides:
        if slide.slide_id == slide_id:
            target_slide = slide
            break

    if not target_slide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Slide '{slide_id}' not found in session '{session_id}'.",
        )

    # Validate field is updatable
    from backend.schemas.input import _UPDATABLE_FIELDS
    if body.field not in _UPDATABLE_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"'{body.field}' is not an updatable field. "
                f"Allowed: {sorted(_UPDATABLE_FIELDS)}"
            ),
        )

    # Apply the update via Pydantic model_copy
    try:
        updated_slide = target_slide.model_copy(update={body.field: body.value})
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Schema validation failed for field '{body.field}': {exc}",
        )

    # Replace the slide in the deck (in-place mutation of the session's deck)
    for i, slide in enumerate(deck.slides):
        if slide.slide_id == slide_id:
            deck.slides[i] = updated_slide
            break
    for i, slide in enumerate(deck.appendix.slides):
        if slide.slide_id == slide_id:
            deck.appendix.slides[i] = updated_slide
            break

    return {
        "session_id": session_id,
        "slide_id": slide_id,
        "field": body.field,
        "status": "updated",
        "message": f"Slide '{slide_id}' field '{body.field}' updated successfully.",
    }


@router.post(
    "/{session_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Mark deck as approved",
)
async def approve_deck(session_id: str) -> dict:
    """Mark the completed deck as approved by the human reviewer.

    Returns 409 if the session is not in COMPLETED state.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)

    if session.status not in (PipelineStatus.COMPLETED, PipelineStatus.COMPLETE):
        raise _conflict(
            f"Only COMPLETED decks can be approved; current status is '{session.status.value}'."
        )

    return {
        "session_id": session_id,
        "status": "approved",
        "message": "Deck approved. Use the /export endpoint to save a versioned copy.",
        "approved_at": datetime.utcnow().isoformat() + "Z",
    }


@router.post(
    "/{session_id}/export",
    status_code=status.HTTP_201_CREATED,
    summary="Export deck to versioned JSON file",
)
async def export_deck(session_id: str) -> dict:
    """Export the completed deck as a versioned JSON file in the export directory.

    Returns 409 if the session is not COMPLETED.
    Returns 404 if no deck is available.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)

    if session.status not in (PipelineStatus.COMPLETED, PipelineStatus.COMPLETE):
        raise _conflict(
            f"Only COMPLETED decks can be exported; current status is '{session.status.value}'."
        )

    if not session.deck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No deck available to export for this session.",
        )

    file_info = await save_deck(session_id, session.deck)

    return {
        "session_id": session_id,
        "status": "exported",
        **file_info,
    }


@router.get(
    "/{session_id}/history",
    status_code=status.HTTP_200_OK,
    summary="List exported versions",
)
async def get_deck_history(
    session_id: str,
    title_slug: Optional[str] = None,
) -> dict:
    """List all exported JSON versions for a deck.

    Optionally filter by title_slug to narrow results to a specific deck title.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)

    versions = await list_versions(session_id, title_slug=title_slug)

    return {
        "session_id": session_id,
        "total_versions": len(versions),
        "versions": versions,
    }
