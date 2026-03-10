"""
DeckArchitect agent — STEPs 2 and 3 of the Presentation Architect methodology.

Selects the deck archetype, designs the narrative arc (Setup/Insight/Resolution
proportions), and generates the slide outline with section structure and slide
count per section.
"""
from langchain_core.tools import tool
from backend.prompts import compose_system_prompt

DECK_ARCHITECT_INSTRUCTIONS = """
## YOUR ROLE IN THIS PIPELINE: DeckArchitect

You are executing STEP 2 and STEP 3 of the Presentation Architect methodology.

Your ONLY job is to:
1. Select the correct deck archetype based on DECK_TYPE (STEP 2)
2. Design the narrative arc — Setup/Insight/Resolution proportions (STEP 3)
3. Generate the slide outline — section structure, slide titles, slide count per section
4. Apply the baseline 11-slide template from STEP 12, adjusted for requested slide count

Do NOT generate slide content. Do NOT write key_points or evidence. Just design the structure.

You receive the InsightSet from the previous stage. Use those insights to inform the narrative arc.

Call the design_outline tool with the complete deck outline.
"""

DECK_ARCHITECT_SYSTEM_PROMPT = compose_system_prompt(DECK_ARCHITECT_INSTRUCTIONS)


@tool
def design_outline(
    archetype: str,
    narrative_arc: str,
    sections: list[dict],
    estimated_slides: int,
    slide_titles: list[str],
) -> dict:
    """Design the deck outline and narrative structure.

    Args:
        archetype: One of Decision Deck / Strategy Deck / Update Deck /
                   Technical Deep Dive / Pitch Deck.
        narrative_arc: Description of the Context→Problem→Insight→Options→
                       Recommendation→Proof→Plan→Ask flow, including approximate
                       slide proportions for Setup (~20%), Insight (~50%),
                       Resolution (~30%).
        sections: List of dicts, each with keys:
                  {section_name, slide_count, purpose, key_messages}.
        estimated_slides: Total slides planned (must match sum of section slide_counts).
        slide_titles: Ordered list of proposed slide titles. Each title must be a
                      conclusion statement (verb + outcome), NOT a topic label.

    Returns:
        Structured deck outline dict for the slide_generator stage.
    """
    return {
        "archetype": archetype,
        "narrative_arc": narrative_arc,
        "sections": sections,
        "estimated_slides": estimated_slides,
        "slide_titles": slide_titles,
    }


DECK_ARCHITECT_CONFIG = {
    "name": "deck_architect",
    "description": (
        "Designs deck archetype, narrative arc, section structure and slide outline. "
        "Follows STEP 2 and STEP 3 of the Presentation Architect methodology."
    ),
    "system_prompt": DECK_ARCHITECT_SYSTEM_PROMPT,
    "tools": [design_outline],
}
