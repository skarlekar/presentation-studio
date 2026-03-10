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

## PIPELINE SEQUENCE

Execute agents in this EXACT order using the task tool:

1. **insight_extractor** — Extract core insights from context and source material
   Input: {context, source_material, audience, deck_type, number_of_slides, tone}

2. **deck_architect** — Design narrative arc and slide outline
   Input: {deck_request, insight_set (from step 1)}

3. **slide_generator** — Generate all main deck slides as structured JSON
   Input: {deck_request, insight_set, deck_outline (from step 2)}
   - Optional: violations list (if regenerating after quality check failure)

4. **appendix_builder** — Generate appendix slides
   Input: {deck_request, slides (from step 3)}

5. **quality_validator** — Validate schema compliance
   Input: {full_deck_json (slides from step 3 + appendix from step 4)}

## QUALITY LOOP

After quality_validator runs:
- If passed=True → pipeline complete, return the final deck JSON
- If passed=False → call slide_generator again with the violations list. Max 3 retries.
- On 4th failure: return deck with validation_warnings field attached listing all violations.

## OUTPUT FORMAT

Return the complete DeckEnvelope JSON as your final response, including:
- session_id
- status: "completed"
- deck: with all main slides and appendix slides
- created_at: ISO-8601 timestamp
"""


def get_checkpointer() -> SqliteSaver:
    """Get or create the SQLite checkpointer for pipeline state persistence."""
    db_path = Path(settings.deepagents_checkpoint_db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver.from_conn_string(str(db_path))


def create_orchestrator():
    """Create and return the compiled orchestrator DeepAgent graph.

    Returns:
        Compiled LangGraph agent graph with HITL interrupts and SQLite checkpointing.
    """
    checkpointer = get_checkpointer()

    orchestrator = create_deep_agent(
        name="deck-orchestrator",
        model=settings.deepagents_model,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        tools=[],  # Only uses built-in task tool for subagent delegation
        interrupt_on={
            "task": True,  # Pause before EVERY subagent call for HITL
        },
        checkpointer=checkpointer,
        response_format=DeckEnvelope,
        subagents=[
            INSIGHT_EXTRACTOR_CONFIG,
            DECK_ARCHITECT_CONFIG,
            SLIDE_GENERATOR_CONFIG,
            APPENDIX_AGENT_CONFIG,
            QUALITY_VALIDATOR_CONFIG,
        ],
    )

    return orchestrator


# Module-level orchestrator instance (initialized lazily to avoid import-time side effects)
_orchestrator = None


def get_orchestrator():
    """Get the singleton orchestrator instance.

    Creates the orchestrator on first call; returns cached instance on subsequent calls.
    Thread-safe for read access (LangGraph graphs are immutable after compilation).
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = create_orchestrator()
    return _orchestrator
