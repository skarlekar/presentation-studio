"""
AppendixBuilder agent — STEP 10 of the Presentation Architect methodology.

Generates appendix slides with supporting data, methodology, and reference
content. Appendix slides follow the identical Slide schema as main slides,
including the one-sentence metaphor requirement.
"""
import json

from langchain_core.tools import tool
from backend.prompts import compose_system_prompt

APPENDIX_AGENT_INSTRUCTIONS = """
## YOUR ROLE IN THIS PIPELINE: AppendixBuilder

You are executing STEP 10 of the Presentation Architect methodology.

Your ONLY job is to generate the appendix slides.

The main deck slides have already been generated and approved. Now you must:
1. Review the main deck for content that was omitted for density reasons
2. Generate appendix slides for: supporting data, secondary insights, methodology, extra charts, reference tables
3. Each appendix slide follows the IDENTICAL schema as main slides (including metaphor)
4. Appendix slide_ids use "A01", "A02", etc.
5. Every appendix slide MUST have a metaphor — exactly 1 sentence
6. section field must be "Appendix" for all appendix slides
7. title: follow TITLE rules from STEP 5 exactly — max 6 words, action-oriented or declarative, Title Case, no period

Allowed layout values: title | two-column | chart | timeline | table | quote | full-bleed visual | framework diagram
Allowed illustration_prompt.type values: process-diagram | architecture-diagram | data-chart | comparison-table | timeline | framework | matrix | before-after

Call the build_appendix tool with the complete appendix slides array as a JSON string.
"""

APPENDIX_AGENT_SYSTEM_PROMPT = compose_system_prompt(APPENDIX_AGENT_INSTRUCTIONS)


@tool
def build_appendix(appendix_slides_json: str) -> dict:
    """Build appendix slides as validated JSON.

    Args:
        appendix_slides_json: JSON array string of appendix slides, each matching
                              the Slide schema exactly.
                              - slide_ids MUST be "A01", "A02", etc.
                              - section field MUST be "Appendix"
                              - Every slide MUST include a metaphor field (1 sentence)
                              - key_points: max 5 items
                              - evidence: max 3 items

    Returns:
        Parsed appendix dict with a 'slides' array, or error dict if JSON is invalid.
    """
    try:
        slides = json.loads(appendix_slides_json)
        if isinstance(slides, list):
            return {"slides": slides}
        elif isinstance(slides, dict):
            return {"slides": slides.get("slides", [])}
        else:
            return {"error": f"Expected JSON array or object, got {type(slides).__name__}", "slides": []}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}", "slides": []}


APPENDIX_AGENT_CONFIG = {
    "name": "appendix_builder",
    "description": (
        "Generates appendix slides with supporting data, methodology, and reference content. "
        "Follows STEP 10 of the Presentation Architect methodology."
    ),
    "system_prompt": APPENDIX_AGENT_SYSTEM_PROMPT,
    "tools": [build_appendix],
}
