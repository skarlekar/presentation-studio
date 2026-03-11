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
import queue as stdlib_queue
import threading
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

    # Strip output_full from agent_steps for the status response (keep it lightweight)
    lightweight_steps = []
    for step in getattr(session, "agent_steps", []):
        lightweight_steps.append({
            "name": step.get("name"),
            "status": step.get("status"),
            "started_at": step.get("started_at"),
            "completed_at": step.get("completed_at"),
            "output_summary": step.get("output_summary"),
        })

    return SessionStatusResponse(
        session_id=session.session_id,
        status=session.status,
        current_stage=session.current_stage,
        slides_generated=slides_generated,
        total_slides=total_slides,
        active_checkpoint=session.current_checkpoint(),
        error=session.error,
        agent_steps=lightweight_steps,
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


def _adapt_raw_deck(data: dict, session_id: str = "") -> Optional[DeckEnvelope]:
    """Adapt whatever JSON the LLM produced into a valid DeckEnvelope.

    The LLM often emits a simplified structure (title, slides with basic fields).
    This function fills in defaults for every missing required field so Pydantic
    validation succeeds even when the LLM omits schema-required fields.
    """
    from backend.schemas.output import (
        Slide, Visual, IllustrationPrompt, Appendix, Deck,
        LayoutType, VisualType, EvidenceType,
    )

    def _default_visual() -> dict:
        return {
            "layout": "two-column",
            "illustration_prompt": {
                "type": "framework",
                "description": "Supporting visual for this slide.",
                "alt_text": "Slide visual",
            },
        }

    def _adapt_slide(raw: dict, index: int) -> dict:
        """Map a raw slide dict to the full Slide schema with defaults."""
        slide_id = raw.get("slide_id") or raw.get("id") or f"{index + 1:02d}"
        # Normalise slide_id: must match ^A?\d{{2,3}}$
        import re as _re
        if not _re.match(r"^A?\d{2,3}$", str(slide_id)):
            slide_id = f"{index + 1:02d}"

        # Extract content text from various common LLM keys
        content_text = (
            raw.get("content") or raw.get("body") or raw.get("narrative") or ""
        )
        bullets = raw.get("bullets") or raw.get("key_points") or raw.get("talking_points") or []
        if isinstance(bullets, str):
            bullets = [b.strip() for b in bullets.split("\n") if b.strip()]

        title = raw.get("title") or f"Slide {index + 1}"
        section = raw.get("section") or (
            "Setup" if index == 0 else "Insight" if index < 4 else "Resolution"
        )
        objective = raw.get("objective") or content_text[:200] or title
        metaphor = raw.get("metaphor") or f"{title}."
        takeaway = raw.get("takeaway") or raw.get("key_message") or title
        speaker_notes = raw.get("speaker_notes") or raw.get("notes") or content_text

        visual = raw.get("visual") or _default_visual()
        if isinstance(visual, dict):
            if "layout" not in visual:
                visual["layout"] = "two-column"
            if "illustration_prompt" not in visual:
                visual["illustration_prompt"] = {
                    "type": "framework",
                    "description": content_text[:200] or "Supporting visual",
                    "alt_text": title,
                }
            elif isinstance(visual["illustration_prompt"], dict):
                ip = visual["illustration_prompt"]
                ip.setdefault("type", "framework")
                ip.setdefault("description", "Supporting visual")
                ip.setdefault("alt_text", title)

        return {
            "slide_id": str(slide_id),
            "section": section,
            "title": title,
            "objective": objective,
            "metaphor": metaphor,
            "key_points": bullets[:5],
            "evidence": [],
            "visual": visual,
            "takeaway": takeaway,
            "speaker_notes": speaker_notes,
            "assets_needed": raw.get("assets_needed", []),
        }

    def _adapt_appendix_slide(raw: dict, index: int) -> dict:
        adapted = _adapt_slide(raw, index)
        # Appendix slides use A01, A02... IDs
        adapted["slide_id"] = raw.get("slide_id") or f"A{index + 1:02d}"
        adapted["section"] = "Appendix"
        return adapted

    try:
        deck_raw = data.get("deck") if isinstance(data, dict) else None
        if not deck_raw or not isinstance(deck_raw, dict):
            return None

        # Adapt slides
        raw_slides = deck_raw.get("slides", [])
        adapted_slides = [_adapt_slide(s, i) for i, s in enumerate(raw_slides) if isinstance(s, dict)]

        # Appendix slides: LLM may use appendix_slides or appendix.slides
        raw_appendix = deck_raw.get("appendix_slides") or deck_raw.get("appendix", {})
        if isinstance(raw_appendix, dict):
            raw_appendix = raw_appendix.get("slides", [])
        if not isinstance(raw_appendix, list):
            raw_appendix = []
        adapted_appendix = [_adapt_appendix_slide(s, i) for i, s in enumerate(raw_appendix) if isinstance(s, dict)]

        adapted_deck = {
            "title": deck_raw.get("title") or "Untitled Deck",
            "type": deck_raw.get("type") or deck_raw.get("deck_type") or "Strategy Deck",
            "audience": deck_raw.get("audience") or "Executive",
            "tone": deck_raw.get("tone") or "Professional",
            "decision_inform_ask": deck_raw.get("decision_inform_ask") or "Inform",
            "context": deck_raw.get("context") or "",
            "source_material_provided": bool(deck_raw.get("source_material_provided", False)),
            "total_slides": len(adapted_slides),
            "slides": adapted_slides,
            "appendix": {"slides": adapted_appendix},
        }

        envelope = {
            "session_id": session_id or data.get("session_id", ""),
            "status": "completed",
            "deck": adapted_deck,
            "created_at": data.get("created_at") or datetime.utcnow().isoformat(),
        }

        return DeckEnvelope.model_validate(envelope)

    except Exception as e:
        logger.warning("_adapt_raw_deck failed: %s", e)
        return None


def _extract_deck_from_result(result: Any, session_id: str = "") -> Optional[DeckEnvelope]:
    """Extract a DeckEnvelope from the orchestrator result.

    Handles three cases:
    1. result IS already a DeckEnvelope (structured output mode)
    2. result is a dict with a "messages" key — parse last message content as JSON
       (plain output mode where the LLM emits a JSON code block)
    3. result is a dict that validates directly as DeckEnvelope

    After parsing, the session_id is always overwritten with the real backend ID.
    """
    def _fixup(env: DeckEnvelope) -> DeckEnvelope:
        """Overwrite any LLM-invented session_id with the real backend ID."""
        if session_id:
            env.session_id = session_id
        return env

    if isinstance(result, DeckEnvelope):
        return _fixup(result)

    if isinstance(result, dict):
        # Walk messages from last to first looking for a parseable DeckEnvelope
        messages = result.get("messages", [])
        for msg in reversed(messages):
            raw_content = getattr(msg, "content", None) or (
                msg.get("content") if isinstance(msg, dict) else None
            )
            if not raw_content:
                continue

            # Normalise content: AIMessage.content can be a plain string OR a list
            # of content blocks like [{"type": "text", "text": "..."}, ...].
            if isinstance(raw_content, list):
                content = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in raw_content
                )
            elif isinstance(raw_content, str):
                content = raw_content
            else:
                content = str(raw_content)

            if not content.strip():
                continue

            data = _extract_json_from_content(content)
            if data:
                try:
                    return _fixup(DeckEnvelope.model_validate(data))
                except Exception as ve:
                    logger.debug("DeckEnvelope validation failed: %s | data keys: %s",
                                 ve, list(data.keys()) if isinstance(data, dict) else type(data))
                    # Deck has many required fields the LLM may omit — try patching defaults
                    deck_data = data.get("deck") if isinstance(data, dict) else None
                    if deck_data and isinstance(deck_data, dict):
                        # Use the full adapter which fills defaults for every required field
                        adapted = _adapt_raw_deck(data, session_id)
                        if adapted:
                            return adapted

        # Try direct dict validation as last resort
        try:
            return _fixup(DeckEnvelope.model_validate(result))
        except Exception:
            pass

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Background pipeline runner
# ─────────────────────────────────────────────────────────────────────────────


def _process_stream_events(events: list, session_id: str, session_svc_sync_steps: list) -> None:
    """Process streaming events to detect agent start/complete (runs in thread).

    Appends dicts like {"action": "start"|"complete", "name": ..., "output": ...}
    to session_svc_sync_steps for the async caller to apply.
    """
    for event in events:
        if not isinstance(event, dict):
            continue
        for _node_name, state_update in event.items():
            if not isinstance(state_update, dict):
                continue
            messages = state_update.get("messages", [])
            if not isinstance(messages, list):
                continue
            for msg in messages:
                # AIMessage with tool_calls → subagent starting
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        if isinstance(tc, dict) and tc.get("name") == "task":
                            agent_name = tc.get("args", {}).get("subagent_type", "")
                            if agent_name:
                                session_svc_sync_steps.append({
                                    "action": "start",
                                    "name": agent_name,
                                })
                # ToolMessage → previous subagent completed
                msg_type = getattr(msg, "type", None)
                if msg_type == "tool":
                    content = getattr(msg, "content", "")
                    if isinstance(content, list):
                        content = " ".join(
                            b.get("text", "") if isinstance(b, dict) else str(b)
                            for b in content
                        )
                    session_svc_sync_steps.append({
                        "action": "complete",
                        "output": str(content)[:5000] if content else None,
                    })


def _extract_messages_from_update(state_update: Any) -> list:
    """Safely extract messages from a LangGraph state update.

    stream_mode="updates" can yield plain dicts OR LangGraph wrapper objects
    (Overwrite, etc.). This function handles both cases.
    """
    # Plain dict (most common)
    if isinstance(state_update, dict):
        msgs = state_update.get("messages", [])
        return msgs if isinstance(msgs, list) else []

    # LangGraph Overwrite / custom wrapper — try common attribute patterns
    for attr in ("messages", "__value__", "value"):
        val = getattr(state_update, attr, None)
        if val is not None:
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                msgs = val.get("messages", [])
                return msgs if isinstance(msgs, list) else []

    return []


def _parse_stream_event(event: Any) -> list[dict]:
    """Extract agent start/complete actions from a single LangGraph stream event.

    Returns a list of action dicts: {"action": "start"|"complete", "name"?: str, "output"?: str}
    """
    if not isinstance(event, dict):
        return []   # Ignore non-dict top-level events (e.g. bare Overwrite objects)

    actions = []
    for _node_name, state_update in event.items():
        for msg in _extract_messages_from_update(state_update):
            # AIMessage with tool_calls → an agent is being called (start)
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in (tool_calls if isinstance(tool_calls, list) else []):
                    name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                    args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                    if name == "task":
                        agent_name = args.get("subagent_type", "")
                        if agent_name:
                            actions.append({"action": "start", "name": agent_name})

            # ToolMessage → the running agent just completed
            msg_type = getattr(msg, "type", None)
            if msg_type == "tool":
                content = getattr(msg, "content", "")
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") if isinstance(b, dict) else str(b)
                        for b in content
                    )
                actions.append({"action": "complete", "output": str(content)[:5000] if content else None})
    return actions


async def run_pipeline(session_id: str, request: DeckRequest) -> None:
    """Run the DeepAgents pipeline with real-time per-agent progress tracking.

    Uses a thread + queue pattern: the stream runs in a background thread and
    puts each event into a Queue as it arrives. The async loop drains the queue
    immediately, updating agent steps after each event — so the UI sees nodes
    light up as each agent completes, not only at the end.
    """
    config = {"configurable": {"thread_id": session_id}}
    orchestrator = get_orchestrator(api_key=request.api_key)
    session_svc = get_session_service()

    try:
        await session_svc.update_status(session_id, PipelineStatus.RUNNING)
        logger.info("Pipeline started for session %s", session_id)

        input_msg = format_deck_request_message(request)

        # ── Real-time streaming via thread + queue ──────────────────────────
        event_q: stdlib_queue.Queue = stdlib_queue.Queue()
        stream_exc: list[Exception] = []

        def _stream_thread():
            try:
                for evt in orchestrator.stream(
                    {"messages": [{"role": "user", "content": input_msg}]},
                    config,
                    stream_mode="updates",
                ):
                    event_q.put(("event", evt))
            except Exception as e:
                stream_exc.append(e)
            finally:
                event_q.put(("done", None))

        t = threading.Thread(target=_stream_thread, daemon=True)
        t.start()

        current_agent: str | None = None

        while True:
            try:
                kind, payload = event_q.get_nowait()
            except stdlib_queue.Empty:
                await asyncio.sleep(0.05)   # yield to event loop, check again
                continue

            if kind == "done":
                break

            # Process this event immediately — updates are visible on the next poll
            for action in _parse_stream_event(payload):
                if action["action"] == "start":
                    agent_name = action["name"]
                    if current_agent and current_agent != agent_name:
                        # Implicitly complete the previous agent
                        await session_svc.complete_agent_step(session_id, current_agent)
                    current_agent = agent_name
                    await session_svc.start_agent_step(session_id, agent_name)
                    await session_svc.update_status(
                        session_id, PipelineStatus.RUNNING, current_stage=agent_name
                    )
                    logger.info("Agent started: %s (session %s)", agent_name, session_id)

                elif action["action"] == "complete" and current_agent:
                    await session_svc.complete_agent_step(
                        session_id, current_agent, output_full=action.get("output")
                    )
                    logger.info("Agent completed: %s (session %s)", current_agent, session_id)
                    current_agent = None

        t.join(timeout=5)

        if stream_exc:
            raise stream_exc[0]

        # Finalise any agent still marked running
        if current_agent:
            await session_svc.complete_agent_step(session_id, current_agent)

        # ── Direct quality validation fallback ──────────────────────────────
        # If quality_validator errored (LLM forgot the required 'description' arg),
        # run the pure-Python validation directly from the agent_steps output.
        session_for_qv = await session_svc.get_session(session_id)
        if session_for_qv:
            qv_step = next(
                (s for s in session_for_qv.agent_steps if s.get("name") == "quality_validator"),
                None,
            )
            sg_step = next(
                (s for s in session_for_qv.agent_steps if s.get("name") == "slide_generator"),
                None,
            )
            if (
                qv_step
                and "description: Field required" in (qv_step.get("output_summary") or "")
                and sg_step
                and sg_step.get("output_full")
            ):
                try:
                    from backend.agents.quality_validator import validate_deck_data
                    # Extract deck JSON from slide_generator output
                    sg_output = sg_step["output_full"]
                    import re as _re
                    fence_m = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", sg_output, _re.DOTALL)
                    if fence_m:
                        deck_json_str = fence_m.group(1)
                    else:
                        brace_start = sg_output.find("{")
                        deck_json_str = sg_output[brace_start:] if brace_start != -1 else ""
                    if deck_json_str:
                        report = validate_deck_data(deck_json_str, session_id)
                        summary = (
                            f"✅ Quality validation passed ({report.total_slides_checked} slides checked)"
                            if report.passed
                            else f"⚠️ {len(report.violations)} violation(s) found across {report.total_slides_checked} slides"
                        )
                        await session_svc.complete_agent_step(
                            session_id, "quality_validator", output_full=summary
                        )
                        logger.info(
                            "Direct quality validation completed for session %s (passed=%s)",
                            session_id, report.passed,
                        )
                except Exception as qv_exc:
                    logger.warning("Direct quality validation fallback failed: %s", qv_exc)

        # ── Extract deck from final state ───────────────────────────────────
        state = await asyncio.to_thread(orchestrator.get_state, config)

        if getattr(state, "next", None):
            stage = _extract_stage_from_state(state)
            pending_input = _extract_pending_input(state)
            await session_svc.add_checkpoint(session_id, stage, pending_input)
            logger.info("Pipeline paused at checkpoint (stage=%s) for session %s", stage, session_id)
        else:
            result_values = getattr(state, "values", {})
            deck = _extract_deck_from_result(result_values, session_id)
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
        # On recursion limit: try to recover the deck from checkpoint message history
        # before marking the session as failed.
        try:
            from langgraph.errors import GraphRecursionError
            if isinstance(exc, GraphRecursionError):
                logger.warning(
                    "Pipeline hit recursion limit for session %s — attempting deck recovery",
                    session_id,
                )
                state = await asyncio.to_thread(orchestrator.get_state, config)
                result_values = getattr(state, "values", {})
                deck = _extract_deck_from_result(result_values, session_id)
                if deck:
                    if current_agent:
                        await session_svc.complete_agent_step(session_id, current_agent)
                    await session_svc.set_deck(session_id, deck)
                    logger.info(
                        "Pipeline recovered from recursion limit for session %s",
                        session_id,
                    )
                    return
        except Exception as recovery_exc:
            logger.warning("Recursion-limit recovery attempt failed: %s", recovery_exc)

        logger.exception("Pipeline error for session %s: %s", session_id, exc)
        session = await session_svc.get_session(session_id)
        if session:
            for step in session.agent_steps:
                if step["status"] == "running":
                    await session_svc.fail_agent_step(session_id, step["name"], error=str(exc))
        await session_svc.update_status(session_id, PipelineStatus.FAILED, error=str(exc))


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

        # Stream events for resume too
        sync_steps: list[dict] = []

        def _run_resume_stream():
            events = list(orchestrator.stream(
                None,
                config,
                stream_mode="updates",
            ))
            _process_stream_events(events, session_id, sync_steps)
            return events

        _events = await asyncio.to_thread(_run_resume_stream)

        # Apply agent step updates
        current_running_agent = None
        for step_action in sync_steps:
            if step_action["action"] == "start":
                agent_name = step_action["name"]
                if current_running_agent and current_running_agent != agent_name:
                    await session_svc.complete_agent_step(session_id, current_running_agent)
                await session_svc.start_agent_step(session_id, agent_name)
                current_running_agent = agent_name
                await session_svc.update_status(
                    session_id, PipelineStatus.RUNNING, current_stage=agent_name
                )
            elif step_action["action"] == "complete":
                if current_running_agent:
                    await session_svc.complete_agent_step(
                        session_id, current_running_agent, output_full=step_action.get("output")
                    )
                    current_running_agent = None

        if current_running_agent:
            await session_svc.complete_agent_step(session_id, current_running_agent)

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
            result = await asyncio.to_thread(orchestrator.get_state, config)
            result_values = getattr(result, "values", {})
            deck = _extract_deck_from_result(result_values, session_id)
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
        session = await session_svc.get_session(session_id)
        if session:
            for step in session.agent_steps:
                if step["status"] == "running":
                    await session_svc.fail_agent_step(session_id, step["name"], error=str(exc))
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


@router.get(
    "/{session_id}/agents",
    summary="Get agent pipeline steps",
)
async def get_agent_steps(session_id: str) -> dict:
    """Return per-agent progress steps for a session.

    Returns the full agent_steps list including output_full for completed agents.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)

    return {
        "session_id": session_id,
        "agent_steps": getattr(session, "agent_steps", []),
    }


@router.get(
    "/{session_id}/agents/{agent_name}",
    summary="Get single agent output",
)
async def get_agent_output(session_id: str, agent_name: str) -> JSONResponse:
    """Return the full output of a specific completed agent step.

    Returns HTML-formatted output suitable for viewing in a new browser tab.
    """
    session_svc = get_session_service()
    session = await session_svc.get_session(session_id)
    if not session:
        raise _session_not_found(session_id)

    AGENT_LABELS = {
        "insight_extractor": "Insight Extraction",
        "deck_architect": "Deck Architecture",
        "slide_generator": "Slide Generation",
        "appendix_builder": "Appendix Builder",
        "quality_validator": "Quality Check",
    }

    for step in getattr(session, "agent_steps", []):
        if step["name"] == agent_name:
            label = AGENT_LABELS.get(agent_name, agent_name)
            output = step.get("output_full") or "No output captured."
            # Return as HTML for viewing in a new tab
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{label} — DeckStudio Agent Output</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 900px; margin: 2rem auto; padding: 0 1.5rem; background: #f8fafc; color: #1e293b; }}
h1 {{ color: #4f46e5; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }}
.meta {{ color: #64748b; font-size: 0.875rem; margin-bottom: 1.5rem; }}
.status {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px;
           font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }}
.status-completed {{ background: #dcfce7; color: #166534; }}
.status-failed {{ background: #fee2e2; color: #991b1b; }}
.status-running {{ background: #dbeafe; color: #1e40af; }}
pre {{ background: #1e293b; color: #e2e8f0; padding: 1.5rem; border-radius: 0.75rem;
       overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; font-size: 0.85rem;
       line-height: 1.6; }}
</style>
</head>
<body>
<h1>🔬 {label}</h1>
<div class="meta">
  <span class="status status-{step.get('status', 'completed')}">{step.get('status', 'unknown')}</span>
  &nbsp; Agent: <code>{agent_name}</code>
  {f' &nbsp; Started: {step.get("started_at", "—")}' if step.get("started_at") else ''}
  {f' &nbsp; Completed: {step.get("completed_at", "—")}' if step.get("completed_at") else ''}
</div>
<pre>{output}</pre>
</body>
</html>"""
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content=html)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Agent '{agent_name}' not found in session '{session_id}'.",
    )


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


@router.get(
    "/exports/all",
    status_code=200,
    summary="List all exported deck versions across all sessions",
)
async def list_all_exports() -> dict:
    """Return a flat list of every exported JSON file in the exports directory.

    Used by the Gallery tab to populate a 'Previous runs' view when no active
    session exists in memory (e.g. after a page refresh or server restart).

    Each entry includes: session_id, filename, title, saved_at, size_bytes, version.
    """
    import json as _json
    from pathlib import Path

    export_dir = Path(settings.export_dir)
    entries = []

    if export_dir.exists():
        for path in sorted(export_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                stat = path.stat()
                # Parse just enough of the file to get title and session_id
                with open(path) as fh:
                    data = _json.load(fh)
                deck = data.get("deck", {})
                entries.append({
                    "filename": path.name,
                    "session_id": data.get("session_id", ""),
                    "title": deck.get("title", "Untitled"),
                    "deck_type": deck.get("type", ""),
                    "total_slides": deck.get("total_slides", len(deck.get("slides", []))),
                    "appendix_slides": len((deck.get("appendix") or {}).get("slides", [])),
                    "saved_at": data.get("created_at", ""),
                    "size_bytes": stat.st_size,
                })
            except Exception:
                continue  # skip malformed files

    return {
        "total": len(entries),
        "exports": entries,
    }


@router.get(
    "/exports/load/{filename}",
    status_code=200,
    summary="Load a specific exported deck JSON by filename",
)
async def load_export(filename: str) -> JSONResponse:
    """Load a previously exported deck JSON from disk and restore it as an active session.

    The filename must match a file in the configured export directory.
    Returns the full DeckEnvelope after creating an in-memory session for it.
    """
    import json as _json
    from pathlib import Path

    # Sanitise: only allow simple filenames, no path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    export_path = Path(settings.export_dir) / filename
    if not export_path.exists():
        raise HTTPException(status_code=404, detail=f"Export file '{filename}' not found.")

    try:
        with open(export_path) as fh:
            data = _json.load(fh)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse export file: {exc}")

    # Restore as a live session
    session_svc = get_session_service()
    preferred_id = data.get("session_id")

    try:
        deck = DeckEnvelope.model_validate(data)
    except Exception:
        deck = _adapt_raw_deck(data, preferred_id or "")
        if not deck:
            raise HTTPException(status_code=422, detail="File does not contain a valid DeckEnvelope.")

    session = await session_svc.create_session({"loaded_from": filename})
    session_id = session.session_id

    if preferred_id and preferred_id != session_id:
        async with session_svc._lock:
            session_svc._sessions[preferred_id] = session
        session_id = preferred_id

    await session_svc.set_deck(session_id, deck)

    return JSONResponse(
        content=_json.loads(deck.model_dump_json()),
        status_code=200,
        headers={"X-Session-Id": session_id},
    )


@router.post(
    "/restore",
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Restore a completed session from a pre-saved recovery JSON file",
)
async def restore_session(
    body: dict = Body(...),
) -> dict:
    """Restore a completed deck session from a recovery JSON object.

    Accepts a full DeckEnvelope-compatible JSON dict (as produced by the recovery
    script) and creates an in-memory completed session. Returns the new session_id.

    Body fields:
      - session_id (optional): preferred session ID to restore under
      - deck: the deck data
    """
    from pathlib import Path

    session_svc = get_session_service()

    # Allow caller to request a specific session_id (for UI continuity)
    preferred_id = body.get("session_id")

    # Try to parse as DeckEnvelope
    try:
        deck = DeckEnvelope.model_validate(body)
    except Exception:
        # Fall back to adapter
        deck = _adapt_raw_deck(body, preferred_id or "")
        if not deck:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not parse body as a valid DeckEnvelope.",
            )

    # Create a new session in COMPLETED state
    session = await session_svc.create_session({"restored": True})
    session_id = session.session_id

    # If a preferred_id was given, swap sessions (best-effort: add under both keys)
    if preferred_id and preferred_id != session_id:
        async with session_svc._lock:
            session_svc._sessions[preferred_id] = session
        session_id = preferred_id

    await session_svc.set_deck(session_id, deck)

    return {
        "session_id": session_id,
        "status": "restored",
        "slides": len(deck.deck.slides) if deck.deck else 0,
        "appendix_slides": len(deck.deck.appendix.slides) if deck.deck and deck.deck.appendix else 0,
        "title": deck.deck.title if deck.deck else None,
        "message": f"Session restored. View at /api/deck/{session_id}",
    }
