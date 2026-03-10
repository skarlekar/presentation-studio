"""
InsightExtractor agent — STEP 1 of the Presentation Architect methodology.

Extracts core insights, themes, problems, and strategic implications from
provided context and source material. Returns a structured InsightSet.
"""
from langchain_core.tools import tool
from backend.prompts import compose_system_prompt
from backend.schemas.output import InsightSet  # noqa: F401 — re-exported for clarity

INSIGHT_EXTRACTOR_INSTRUCTIONS = """
## YOUR ROLE IN THIS PIPELINE: InsightExtractor

You are executing STEP 1 of the Presentation Architect methodology.

Your ONLY job in this call is to:
1. Analyze the provided CONTEXT and SOURCE_MATERIAL (if provided)
2. Extract 3-5 core insights following STEP 1 exactly
3. Return a structured InsightSet

Focus exclusively on STEP 1 — Extract Insights From Documents.
Do NOT generate slides. Do NOT design the outline. Just extract insights.

Output format — call the extract_insights tool with:
{
  "core_problem": "One sentence describing the fundamental problem or opportunity",
  "key_insights": ["insight1", "insight2", "insight3"],  // max 5
  "supporting_evidence": ["evidence1", "evidence2"],
  "strategic_options": ["option1", "option2"],
  "risks_constraints": ["risk1", "risk2"],
  "implications": ["implication1", "implication2"]
}
"""

INSIGHT_EXTRACTOR_SYSTEM_PROMPT = compose_system_prompt(INSIGHT_EXTRACTOR_INSTRUCTIONS)


@tool
def extract_insights(
    core_problem: str,
    key_insights: list[str],
    supporting_evidence: list[str],
    strategic_options: list[str],
    risks_constraints: list[str],
    implications: list[str],
) -> dict:
    """Extract and structure core insights from context and source material.

    Call this tool with the extracted insights after analyzing all provided material.
    Returns the structured InsightSet for the next pipeline stage.

    Args:
        core_problem: One sentence describing the fundamental problem or opportunity.
        key_insights: List of 3-5 core insights that drive the deck narrative.
        supporting_evidence: Metrics, quotes, benchmarks extracted from source material.
        strategic_options: Possible approaches suggested by the material.
        risks_constraints: Operational, technical, financial, or organisational barriers.
        implications: Decisions that logically follow from the analysis.

    Returns:
        Structured InsightSet dict for downstream pipeline stages.
    """
    return {
        "core_problem": core_problem,
        "key_insights": key_insights[:5],  # enforce max 5
        "supporting_evidence": supporting_evidence,
        "strategic_options": strategic_options,
        "risks_constraints": risks_constraints,
        "implications": implications,
    }


INSIGHT_EXTRACTOR_CONFIG = {
    "name": "insight_extractor",
    "description": (
        "Extracts core insights, themes, problems, and strategic implications from provided "
        "context and source material. Follows STEP 1 of the Presentation Architect methodology."
    ),
    "system_prompt": INSIGHT_EXTRACTOR_SYSTEM_PROMPT,
    "tools": [extract_insights],
}
