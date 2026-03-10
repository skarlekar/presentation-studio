"""
SlideGenerator agent — STEPs 4, 5, 6, 7, 8, 9, 12, and 13 of the
Presentation Architect methodology.

Generates ALL main deck slides as structured JSON exactly matching the
DeckEnvelope schema. Every slide must include a one-sentence metaphor,
max 5 key_points, and max 3 evidence items.
"""
import json

from langchain_core.tools import tool
from backend.prompts import compose_system_prompt

SLIDE_GENERATOR_INSTRUCTIONS = """
## YOUR ROLE IN THIS PIPELINE: SlideGenerator

You are executing STEPs 4, 5, 6, 7, 8, 9, 12, and 13 of the Presentation Architect methodology.

Your job is to generate ALL slides as structured JSON exactly matching the schema in STEP 9.

CRITICAL RULES (enforced by schema validation — violations will trigger regeneration):
1. Every slide MUST have a metaphor — exactly 1 sentence, plain language, from that slide's specific content
2. key_points: maximum 5 items per slide
3. evidence: maximum 3 items per slide
4. title: must be a conclusion statement (verb + outcome), never a topic label
5. Slide 2 MUST be the Executive Summary (STEP 4) with exactly 5 bullets
6. Follow narrative arc proportions from the provided outline (Setup ~20%, Insight ~50%, Resolution ~30%)
7. Every slide needs a visual plan with layout and illustration_prompt

Allowed layout values: title | two-column | chart | timeline | table | quote | full-bleed visual | framework diagram
Allowed illustration_prompt.type values: process-diagram | architecture-diagram | data-chart | comparison-table | timeline | framework | matrix | before-after

You receive:
- The original DeckRequest (context, audience, tone, deck_type, etc.)
- The InsightSet from stage 1
- The DeckOutline from stage 2
- Optional: violations list (if regenerating after quality check failure)

Call the generate_slides tool with the complete DeckEnvelope JSON string.
The JSON must include the full deck with all main slides.
The appendix_builder agent will add appendix slides separately.
"""

SLIDE_GENERATOR_SYSTEM_PROMPT = compose_system_prompt(SLIDE_GENERATOR_INSTRUCTIONS)


@tool
def generate_slides(slides_json: str) -> dict:
    """Generate all main deck slides as validated JSON matching the DeckEnvelope schema.

    Args:
        slides_json: Complete JSON string matching the DeckEnvelope schema from STEP 9.
                    Must include all main slides (appendix will be added by appendix_builder).
                    Every slide must have:
                    - metaphor: exactly 1 sentence
                    - key_points: max 5 items
                    - evidence: max 3 items
                    - title: conclusion statement (verb + outcome)
                    - visual.layout: one of 8 allowed layouts
                    - visual.illustration_prompt.type: one of 8 allowed visual types

    Returns:
        Parsed deck envelope dict, or error dict if JSON is invalid.
    """
    try:
        return json.loads(slides_json)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}", "raw": slides_json[:500]}


SLIDE_GENERATOR_CONFIG = {
    "name": "slide_generator",
    "description": (
        "Generates all presentation slides as structured JSON following the Presentation "
        "Architect schema. Follows STEPs 4-9 and 12-13."
    ),
    "system_prompt": SLIDE_GENERATOR_SYSTEM_PROMPT,
    "tools": [generate_slides],
}
