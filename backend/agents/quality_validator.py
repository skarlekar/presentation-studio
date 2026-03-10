"""
QualityValidator agent — STEP 9 field rules and OUTPUT COMPLETENESS RULES.

Contains REAL Python validation logic (not just LLM reasoning). Validates the
generated deck against all schema constraints and returns a ValidationReport.
"""
import json
import re
from datetime import datetime

from langchain_core.tools import tool
from backend.prompts import compose_system_prompt
from backend.schemas.output import ValidationReport, Violation, ViolationSeverity

QUALITY_VALIDATOR_INSTRUCTIONS = """
## YOUR ROLE IN THIS PIPELINE: QualityValidator

You are executing the quality validation stage using STEP 9 FIELD RULES and OUTPUT COMPLETENESS RULES.

Your job is to validate the generated deck against ALL schema constraints:
1. metaphor: exactly 1 sentence on every slide (including appendix)
2. key_points: max 5 items per slide
3. evidence: max 3 items per slide
4. title: must be a conclusion statement (should contain a verb and an outcome)
5. All required fields present and non-empty
6. slide_id format: main slides "01"-"NN", appendix "A01", "A02" etc.
7. visual.layout: must be one of the 8 allowed layout types
8. illustration_prompt.type: must be one of the 8 allowed visual types

Allowed layout values: title | two-column | chart | timeline | table | quote | full-bleed visual | framework diagram
Allowed illustration_prompt.type values: process-diagram | architecture-diagram | data-chart | comparison-table | timeline | framework | matrix | before-after

Call the validate_deck tool with the full deck JSON to get a ValidationReport.
The tool contains real Python validation logic — trust its output.
If the report shows valid=False (passed=False), list all violations clearly.
"""

QUALITY_VALIDATOR_SYSTEM_PROMPT = compose_system_prompt(QUALITY_VALIDATOR_INSTRUCTIONS)

ALLOWED_LAYOUTS = frozenset({
    "title",
    "two-column",
    "chart",
    "timeline",
    "table",
    "quote",
    "full-bleed visual",
    "framework diagram",
})

ALLOWED_VISUAL_TYPES = frozenset({
    "process-diagram",
    "architecture-diagram",
    "data-chart",
    "comparison-table",
    "timeline",
    "framework",
    "matrix",
    "before-after",
})

# Common abbreviations to ignore when sentence-splitting
_ABBREV_PATTERN = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|i\.e|e\.g|Fig|No|Vol|Ch|Dept)\.\s",
    re.IGNORECASE,
)


def _count_sentences(text: str) -> int:
    """Count sentences in text, ignoring common abbreviations."""
    cleaned = _ABBREV_PATTERN.sub(lambda m: m.group(0).replace(". ", "_ABBREV "), text)
    parts = re.split(r"(?<=[.!?])\s+", cleaned.strip())
    return len([s for s in parts if s.strip()])


def _make_violation(
    slide_id: str,
    field: str,
    rule: str,
    value_preview: str = "",
) -> Violation:
    """Helper to create an ERROR-severity Violation."""
    return Violation(
        slide_id=slide_id,
        field=field,
        rule=rule,
        severity=ViolationSeverity.ERROR,
        value_preview=value_preview[:200] if value_preview else None,
    )


def validate_deck_data(deck_json: str, session_id: str = "") -> ValidationReport:
    """Pure Python validation of a deck JSON string against all schema constraints.

    Args:
        deck_json: Complete DeckEnvelope JSON string to validate.
        session_id: Optional session identifier included in the report.

    Returns:
        ValidationReport with passed bool and full violation list.
    """
    violations: list[Violation] = []

    try:
        data = json.loads(deck_json)
    except json.JSONDecodeError as e:
        return ValidationReport(
            session_id=session_id,
            passed=False,
            total_slides_checked=0,
            violations=[
                _make_violation("ALL", "json", f"JSON parse error: {e}")
            ],
        )

    # Support both wrapped {"deck": {...}} and unwrapped deck objects
    deck = data.get("deck", data) if isinstance(data, dict) else {}

    main_slides: list[dict] = deck.get("slides", [])
    appendix_slides: list[dict] = (
        deck.get("appendix", {}).get("slides", [])
        if isinstance(deck.get("appendix"), dict)
        else []
    )
    all_slides = main_slides + appendix_slides

    for slide in all_slides:
        if not isinstance(slide, dict):
            violations.append(_make_violation("UNKNOWN", "slide", "Slide entry is not a JSON object"))
            continue

        sid = slide.get("slide_id", "?")

        # ── metaphor ────────────────────────────────────────────────────────
        metaphor = slide.get("metaphor", "")
        if not metaphor or not str(metaphor).strip():
            violations.append(_make_violation(sid, "metaphor", "metaphor is required and must not be empty"))
        else:
            count = _count_sentences(str(metaphor))
            if count > 1:
                violations.append(_make_violation(
                    sid, "metaphor",
                    f"metaphor must be exactly 1 sentence; detected {count} sentences",
                    str(metaphor)[:200],
                ))

        # ── key_points ──────────────────────────────────────────────────────
        kp = slide.get("key_points", [])
        if isinstance(kp, list) and len(kp) > 5:
            violations.append(_make_violation(
                sid, "key_points",
                f"key_points must not exceed 5 items; found {len(kp)}",
                str(len(kp)),
            ))

        # ── evidence ────────────────────────────────────────────────────────
        ev = slide.get("evidence", [])
        if isinstance(ev, list) and len(ev) > 3:
            violations.append(_make_violation(
                sid, "evidence",
                f"evidence must not exceed 3 items per slide; found {len(ev)}",
                str(len(ev)),
            ))

        # ── required non-empty string fields ────────────────────────────────
        for field_name in ("title", "objective", "takeaway", "section"):
            val = slide.get(field_name, "")
            if not isinstance(val, str) or not val.strip():
                violations.append(_make_violation(
                    sid, field_name,
                    f"{field_name} is required and must not be empty",
                ))

        # ── visual.layout ────────────────────────────────────────────────────
        visual = slide.get("visual", {})
        if not isinstance(visual, dict):
            violations.append(_make_violation(sid, "visual", "visual must be an object"))
        else:
            layout = visual.get("layout", "")
            if layout not in ALLOWED_LAYOUTS:
                violations.append(_make_violation(
                    sid, "visual.layout",
                    f"layout '{layout}' is not allowed; must be one of: {', '.join(sorted(ALLOWED_LAYOUTS))}",
                    layout,
                ))

            # ── illustration_prompt.type ─────────────────────────────────────
            ip = visual.get("illustration_prompt", {})
            if not isinstance(ip, dict):
                violations.append(_make_violation(sid, "illustration_prompt", "illustration_prompt must be an object"))
            else:
                ip_type = ip.get("type", "")
                if ip_type not in ALLOWED_VISUAL_TYPES:
                    violations.append(_make_violation(
                        sid, "illustration_prompt.type",
                        f"visual type '{ip_type}' is not allowed; must be one of: {', '.join(sorted(ALLOWED_VISUAL_TYPES))}",
                        ip_type,
                    ))

    return ValidationReport(
        session_id=session_id,
        passed=len(violations) == 0,
        total_slides_checked=len(all_slides),
        violations=violations,
    )


@tool
def validate_deck(deck_json: str) -> dict:
    """Validate the complete deck JSON against all Presentation Architect schema constraints.

    Performs real Python validation (not LLM reasoning) against these rules:
    - metaphor: exactly 1 sentence on every slide
    - key_points: max 5 items per slide
    - evidence: max 3 items per slide
    - title, objective, takeaway, section: required and non-empty
    - visual.layout: must be one of 8 allowed layout types
    - illustration_prompt.type: must be one of 8 allowed visual types

    Args:
        deck_json: Complete DeckEnvelope JSON string to validate.

    Returns:
        ValidationReport dict. Key fields:
        - passed (bool): True if no ERROR violations found
        - total_slides_checked (int): Number of slides validated
        - violations (list): All found violations with field, rule, value_preview
    """
    report = validate_deck_data(deck_json)
    return report.model_dump()


QUALITY_VALIDATOR_CONFIG = {
    "name": "quality_validator",
    "description": (
        "Validates all slides against Presentation Architect schema constraints: "
        "metaphor=1 sentence, key_points≤5, evidence≤3, required fields, layout types, visual types."
    ),
    "system_prompt": QUALITY_VALIDATOR_SYSTEM_PROMPT,
    "tools": [validate_deck],
}
