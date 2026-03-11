"""
DeckStudio Orchestrator — DeepAgents pipeline with HITL.

Architecture:
  - One orchestrator agent with 5 registered subagents.
  - HITL: interrupt_on={"task": True} pauses before each subagent delegation.
  - Checkpointing: SqliteSaver for durable state (survives restarts).

Pipeline sequence:
  1. insight_extractor  → extract core insights (STEP 1)
  2. deck_architect     → design narrative arc + outline (STEPs 2-3)
  3. slide_generator    → generate all slides (STEPs 4-9, 12-13)
  4. appendix_builder   → generate appendix slides (STEP 10)
  5. quality_validator  → validate schema compliance (STEP 9 rules)
"""
from pathlib import Path

from deepagents import create_deep_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
import sqlite3

from backend.config.settings import get_settings
from backend.agents.insight_extractor import INSIGHT_EXTRACTOR_CONFIG
from backend.agents.deck_architect import DECK_ARCHITECT_CONFIG
from backend.agents.slide_generator import SLIDE_GENERATOR_CONFIG
from backend.agents.appendix_agent import APPENDIX_AGENT_CONFIG
from backend.agents.quality_validator import QUALITY_VALIDATOR_CONFIG
from backend.schemas.output import DeckEnvelope

settings = get_settings()

ORCHESTRATOR_SYSTEM_PROMPT = """
You are the DeckStudio Pipeline Orchestrator. Your job is to coordinate 5 specialized agents
in sequence to produce a complete, validated presentation deck.

## HOW TO CALL THE TASK TOOL

The task tool requires subagent_type. Always include a brief description of what you want done.
  - subagent_type: the agent name (e.g. "quality_validator")
  - description: a short plain-text instruction for the agent (no need to repeat large JSON blobs)

Examples:
  task(subagent_type="quality_validator", description="Validate the deck from previous steps.")
  task(subagent_type="insight_extractor", description="Extract insights from the source material above.")

## PIPELINE SEQUENCE

Execute agents in this EXACT order using the task tool.
Each agent receives its context via the `description` parameter (a plain text string):

1. **insight_extractor** — Extract core insights from context and source material
   description should include: context, source_material, audience, deck_type, number_of_slides, tone

2. **deck_architect** — Design narrative arc and slide outline
   description should include: deck_request, insight_set (from step 1)

3. **slide_generator** — Generate all main deck slides as structured JSON
   description should include: deck_request, insight_set, deck_outline (from step 2)
   - Optional: violations list (if regenerating after quality check failure)

4. **appendix_builder** — Generate appendix slides
   description should include: deck_request, slides JSON (from step 3)

5. **quality_validator** — Validate schema compliance
   description should be a SHORT instruction only — do NOT paste the deck JSON here.
   The validator reads the deck directly from the conversation history.
   Example: task(subagent_type="quality_validator", description="Validate the deck from previous steps.")

## QUALITY LOOP

After quality_validator runs:
- If passed=True → pipeline complete, return the final deck JSON
- If passed=False → call slide_generator again with the violations list. Max 3 retries.
- On 4th failure: return deck with validation_warnings field attached listing all violations.

## OUTPUT FORMAT

When the pipeline is complete, emit your FINAL response as a raw JSON code block with no
surrounding commentary. The JSON must conform to the DeckEnvelope schema:

```json
{
  "session_id": "<session_id>",
  "status": "completed",
  "created_at": "<ISO-8601 timestamp>",
  "deck": {
    "title": "...",
    "slides": [...],
    "appendix_slides": [...]
  }
}
```

IMPORTANT: Your absolute last message must be ONLY the ```json ... ``` code block.
Do not add any explanation before or after the JSON block in your final message.
"""


def get_checkpointer() -> SqliteSaver:
    """Get or create the SQLite checkpointer for pipeline state persistence.

    Creates a direct sqlite3 connection — from_conn_string() is a context manager
    and cannot be used directly as a checkpointer argument.
    """
    db_path = Path(settings.deepagents_checkpoint_db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()  # Create checkpoint tables if they don't exist
    return checkpointer


def _build_llm(api_key: str | None = None):
    """Construct the LLM client for the orchestrator.

    Builds a typed LangChain model instance so the API key is passed explicitly
    rather than relying on environment variable lookup (which can miss runtime
    keys supplied per-request from the frontend).

    Args:
        api_key: Anthropic or OpenAI API key, either from env or from the request.

    Returns:
        A configured ChatAnthropic or ChatOpenAI instance.
    """
    key = api_key or settings.active_api_key
    if settings.llm_provider == "anthropic":
        kwargs = dict(
            model_name=settings.anthropic_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )
        if key:
            kwargs["api_key"] = key
        return ChatAnthropic(**kwargs)
    else:
        kwargs = dict(
            model=settings.openai_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )
        if key:
            kwargs["api_key"] = key
        return ChatOpenAI(**kwargs)


def create_orchestrator(api_key: str | None = None):
    """Create and return the compiled orchestrator DeepAgent graph.

    Args:
        api_key: Optional API key supplied at request time (when not in env).

    Returns:
        Compiled LangGraph agent graph with HITL interrupts and SQLite checkpointing.
    """
    checkpointer = get_checkpointer()
    model = _build_llm(api_key)

    orchestrator = create_deep_agent(
        name="deck-orchestrator",
        model=model,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        tools=[],  # Only uses built-in task tool for subagent delegation
        # interrupt_on intentionally omitted: per-subagent HITL creates 5+ identical modals
        # with no stage context, creating a confusing UX. Human review happens once via
        # the Gallery tab "Approve" button after the full deck is generated.
        checkpointer=checkpointer,
        # response_format intentionally omitted: Anthropic's grammar compiler rejects the
        # combination of DeckEnvelope schema + subagent task tools (too many tools + complex
        # schema = "compiled grammar too large"). Instead, the system prompt instructs the
        # orchestrator to emit a JSON code block as its final message, which deck.py parses
        # via _extract_deck_from_result().
        subagents=[
            INSIGHT_EXTRACTOR_CONFIG,
            DECK_ARCHITECT_CONFIG,
            SLIDE_GENERATOR_CONFIG,
            APPENDIX_AGENT_CONFIG,
            QUALITY_VALIDATOR_CONFIG,
        ],
    )

    return orchestrator


# Module-level orchestrator instance (initialized lazily)
# When a user-supplied API key is used, a fresh orchestrator is created per-session
# to ensure the key is properly applied.
_orchestrator = None


def get_orchestrator(api_key: str | None = None):
    """Get the orchestrator instance.

    - If api_key is provided AND no env key is set: creates a new orchestrator with
      the user-supplied key applied to the environment for this process.
    - Otherwise: returns the cached singleton.

    Args:
        api_key: Optional Anthropic API key from the frontend request.

    Returns:
        Compiled LangGraph agent graph ready for invocation.
    """
    global _orchestrator

    # If a key is supplied from the frontend and not already in env, apply it
    # Always create a fresh orchestrator when a user-supplied key is provided,
    # so the explicit key is baked into the LLM client (not env-var dependent).
    if api_key:
        return create_orchestrator(api_key)

    if _orchestrator is None:
        _orchestrator = create_orchestrator()
    return _orchestrator
