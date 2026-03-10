"""
Prompt loader for DeckStudio.
Loads the Presentation Architect Prompt at import time (fail-fast).
"""
from pathlib import Path

_PROMPT_FILE = Path(__file__).parent / "presentation_architect.txt"

if not _PROMPT_FILE.exists():
    raise FileNotFoundError(
        f"Presentation Architect Prompt not found at {_PROMPT_FILE}. "
        "This file is required for all agent operations. "
        "See PROMPT_ARCHITECTURE.md for details."
    )

PRESENTATION_ARCHITECT_PROMPT: str = _PROMPT_FILE.read_text(encoding="utf-8")


def compose_system_prompt(agent_instructions: str) -> str:
    """
    Compose a complete system prompt for an agent.
    Returns: Presentation Architect Prompt + agent-specific instructions.
    """
    return PRESENTATION_ARCHITECT_PROMPT + "\n\n" + agent_instructions
