"""
CI gate test — CRITICAL.

Verifies that ALL 5 agents' system prompts contain canonical Presentation Architect
Prompt key phrases. This ensures no agent LLM call can happen without the full prompt.

If this test fails, it means an agent was built without the canonical prompt.
Do not merge — regenerate the agent using compose_system_prompt().
"""
import pytest

from prompts import PRESENTATION_ARCHITECT_PROMPT, compose_system_prompt
from agents.insight_extractor import INSIGHT_EXTRACTOR_SYSTEM_PROMPT
from agents.deck_architect import DECK_ARCHITECT_SYSTEM_PROMPT
from agents.slide_generator import SLIDE_GENERATOR_SYSTEM_PROMPT
from agents.appendix_agent import APPENDIX_AGENT_SYSTEM_PROMPT
from agents.quality_validator import QUALITY_VALIDATOR_SYSTEM_PROMPT


# ── Canonical prompt sanity check ─────────────────────────────────────────────

CANONICAL_KEY_PHRASES = [
    # STEP 1 markers
    "STEP 1",
    "Extract Insights",
    # STEP 2 markers
    "STEP 2",
    "Archetype",
    # STEP 3 markers
    "STEP 3",
    "Narrative Story Arc",
    # STEP 9 markers
    "STEP 9",
    # HARD RULES section
    "HARD RULES",
    # Key schema constraints
    "key_points",
    "evidence",
    "metaphor",
    "exactly 1 sentence",
    # Allowed layouts
    "two-column",
    "framework diagram",
    # Allowed visual types
    "data-chart",
    "process-diagram",
]


class TestCanonicalPromptLoaded:
    """Verify the canonical prompt file is loaded correctly."""

    def test_prompt_is_non_empty(self):
        assert PRESENTATION_ARCHITECT_PROMPT, "Presentation Architect Prompt is empty"
        assert len(PRESENTATION_ARCHITECT_PROMPT) > 1000, (
            f"Prompt is suspiciously short ({len(PRESENTATION_ARCHITECT_PROMPT)} chars)"
        )

    @pytest.mark.parametrize("phrase", CANONICAL_KEY_PHRASES)
    def test_canonical_prompt_contains_phrase(self, phrase: str):
        """Each key phrase must be present in the canonical prompt."""
        assert phrase in PRESENTATION_ARCHITECT_PROMPT, (
            f"Canonical prompt missing key phrase: {phrase!r}. "
            f"This indicates the prompt file may have been truncated or modified."
        )


class TestComposeSystemPrompt:
    """Verify compose_system_prompt() correctly prepends the canonical prompt."""

    def test_returns_string(self):
        result = compose_system_prompt("My agent instructions.")
        assert isinstance(result, str)

    def test_contains_canonical_prompt(self):
        result = compose_system_prompt("My agent instructions.")
        assert PRESENTATION_ARCHITECT_PROMPT in result

    def test_contains_agent_specific_instructions(self):
        specific = "My unique agent-specific instructions for testing."
        result = compose_system_prompt(specific)
        assert specific in result

    def test_canonical_prompt_comes_first(self):
        specific = "Agent-specific part."
        result = compose_system_prompt(specific)
        arch_idx = result.index(PRESENTATION_ARCHITECT_PROMPT[:50])
        specific_idx = result.index(specific)
        assert arch_idx < specific_idx, (
            "Canonical prompt must appear BEFORE agent-specific instructions"
        )


# ── Gate test: every agent must contain canonical prompt ─────────────────────

ALL_AGENT_PROMPTS = [
    ("insight_extractor", INSIGHT_EXTRACTOR_SYSTEM_PROMPT),
    ("deck_architect", DECK_ARCHITECT_SYSTEM_PROMPT),
    ("slide_generator", SLIDE_GENERATOR_SYSTEM_PROMPT),
    ("appendix_builder", APPENDIX_AGENT_SYSTEM_PROMPT),
    ("quality_validator", QUALITY_VALIDATOR_SYSTEM_PROMPT),
]


class TestAllAgentsContainCanonicalPrompt:
    """
    CI GATE: Every agent's system prompt MUST contain the full canonical
    Presentation Architect Prompt. No exceptions.
    """

    @pytest.mark.parametrize("agent_name,system_prompt", ALL_AGENT_PROMPTS)
    def test_agent_contains_canonical_prompt(self, agent_name: str, system_prompt: str):
        """Agent system prompt must contain the full Presentation Architect Prompt."""
        assert PRESENTATION_ARCHITECT_PROMPT in system_prompt, (
            f"CRITICAL: {agent_name} system prompt does NOT contain the canonical "
            f"Presentation Architect Prompt. This violates the core design constraint. "
            f"Rebuild {agent_name} using compose_system_prompt()."
        )

    @pytest.mark.parametrize("agent_name,system_prompt", ALL_AGENT_PROMPTS)
    @pytest.mark.parametrize("phrase", CANONICAL_KEY_PHRASES[:5])  # spot-check 5 phrases
    def test_agent_contains_key_phrase(self, agent_name: str, system_prompt: str, phrase: str):
        """Each key phrase from the canonical prompt must appear in every agent."""
        assert phrase in system_prompt, (
            f"{agent_name} is missing canonical phrase: {phrase!r}"
        )

    @pytest.mark.parametrize("agent_name,system_prompt", ALL_AGENT_PROMPTS)
    def test_agent_prompt_minimum_length(self, agent_name: str, system_prompt: str):
        """All agent prompts must be at least as long as the canonical prompt itself."""
        assert len(system_prompt) >= len(PRESENTATION_ARCHITECT_PROMPT), (
            f"{agent_name} prompt ({len(system_prompt)} chars) is shorter than "
            f"canonical prompt ({len(PRESENTATION_ARCHITECT_PROMPT)} chars). "
            f"This should be impossible if compose_system_prompt() was used."
        )
