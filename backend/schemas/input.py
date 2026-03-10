"""
DeckStudio — Input Schemas (Pydantic v2).

These models validate all data arriving at the API boundary:
  • DeckRequest       — initial deck generation request
  • SlideUpdateRequest — human edit to a single slide field
  • CheckpointApproveRequest — human approves a pipeline checkpoint
  • CheckpointRejectRequest  — human rejects / requests changes at a checkpoint
  • GenerateResponse   — immediate acknowledgement returned on request acceptance
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────


class DeckType(str, Enum):
    """
    Valid deck archetypes.  Maps to STEP 2 in the Presentation Architect Prompt.
    """

    DECISION = "Decision Deck"
    STRATEGY = "Strategy Deck"
    UPDATE = "Update Deck"
    TECHNICAL = "Technical Deep Dive"
    PITCH = "Pitch Deck"


class DecisionInformAsk(str, Enum):
    """
    The primary intent of the deck — what the presenter wants from the audience.
    """

    DECISION = "Decision"
    INFORM = "Inform"
    ASK = "Ask"


# ─────────────────────────────────────────────────────────────────────────────
# Shared validators
# ─────────────────────────────────────────────────────────────────────────────


def _count_sentences(text: str) -> int:
    """
    Rough sentence count using terminal punctuation as the heuristic.
    Used to enforce the "exactly 1 sentence" rule on metaphor fields.
    """
    # Strip whitespace and split on sentence-ending punctuation.
    sentences = re.split(r"[.!?]+", text.strip())
    # Filter out empty strings produced by trailing punctuation.
    return len([s for s in sentences if s.strip()])


def _validate_single_sentence(value: str, field_name: str = "field") -> str:
    """
    Raise ValueError if *value* contains more than one sentence.
    Allows a single trailing punctuation mark.
    """
    count = _count_sentences(value)
    if count > 1:
        raise ValueError(
            f"'{field_name}' must be exactly 1 sentence; "
            f"detected {count} sentences in: {value!r}"
        )
    return value


def _validate_non_empty_string(value: str | None, field_name: str = "field") -> str:
    """Raise ValueError if value is None or blank."""
    if not value or not value.strip():
        raise ValueError(f"'{field_name}' must not be empty or blank.")
    return value.strip()


# ─────────────────────────────────────────────────────────────────────────────
# DeckRequest
# ─────────────────────────────────────────────────────────────────────────────


class DeckRequest(BaseModel):
    """
    The primary input for a new deck generation session.

    At least one of ``context`` or ``source_material`` must be provided.
    All required fields mirror the REQUIRED INPUTS block in the Presentation
    Architect Prompt.
    """

    # ── Required ────────────────────────────────────────────────────────────

    context: str | None = Field(
        default=None,
        description=(
            "Background, situation, purpose, and framing for the deck. "
            "May be provided alone (without source_material) or combined with it. "
            "At least one of context or source_material is required."
        ),
        examples=["We need to present the business case for migrating to a cloud-native data platform."],
    )

    number_of_slides: int = Field(
        ...,
        ge=3,
        le=60,
        description="Total number of main-deck slides to generate (3–60).",
        examples=[11],
    )

    audience: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Who will view the deck (role, seniority, technical level, organisation).",
        examples=["C-suite executives at a Fortune 500 financial services firm"],
    )

    deck_type: DeckType = Field(
        ...,
        description="Deck archetype. Drives narrative structure and visual emphasis.",
        examples=[DeckType.DECISION],
    )

    decision_inform_ask: DecisionInformAsk = Field(
        ...,
        description="Primary intent: what the presenter wants from the audience.",
        examples=[DecisionInformAsk.DECISION],
    )

    tone: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description=(
            "Desired language register and communication style. "
            "Examples: 'authoritative and data-driven', 'confident but approachable', "
            "'urgent and direct'."
        ),
        examples=["Authoritative, data-driven, executive-grade"],
    )

    # ── Optional ─────────────────────────────────────────────────────────────

    source_material: str | None = Field(
        default=None,
        description=(
            "Documents, research, transcripts, or notes to analyse. "
            "Optional when context is provided. Pasted as plain text; "
            "use the /upload endpoint for binary files."
        ),
    )

    must_include_sections: list[str] | None = Field(
        default=None,
        description=(
            "Section titles or topics that MUST appear in the deck. "
            "Defaults to the standard 11-slide outline when omitted."
        ),
        examples=[["Executive Summary", "Risk & Mitigations", "Decision / CTA"]],
    )

    brand_style_guide: str | None = Field(
        default=None,
        description=(
            "Brand or visual style instructions for the deck. "
            "Defaults to minimal consulting style (2–3 colour palette, flat icons)."
        ),
    )

    top_messages: list[str] | None = Field(
        default=None,
        max_length=5,
        description=(
            "Up to 5 key messages the deck must land. "
            "Derived from context/source_material when omitted."
        ),
    )

    known_metrics: list[str] | None = Field(
        default=None,
        description=(
            "Known quantitative proof points to prioritise as evidence. "
            "Extracted from source material when omitted."
        ),
    )

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("context", mode="before")
    @classmethod
    def _strip_context(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @field_validator("source_material", mode="before")
    @classmethod
    def _strip_source_material(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @model_validator(mode="after")
    def _at_least_one_of_context_or_source_material(self) -> "DeckRequest":
        if not self.context and not self.source_material:
            raise ValueError(
                "At least one of 'context' or 'source_material' must be provided. "
                "Both may be None only if neither was supplied — the prompt requires at least one."
            )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# SlideUpdateRequest
# ─────────────────────────────────────────────────────────────────────────────


_UPDATABLE_FIELDS = frozenset(
    {
        "title",
        "objective",
        "metaphor",
        "key_points",
        "evidence",
        "takeaway",
        "speaker_notes",
        "assets_needed",
        "visual",
    }
)


class SlideUpdateRequest(BaseModel):
    """
    Human-authored edit to a single field on a slide.

    The agent pipeline applies this update, re-validates the slide schema,
    then continues generation.
    """

    session_id: str = Field(
        ...,
        description="Active generation session identifier.",
    )

    slide_id: str = Field(
        ...,
        description="Zero-padded slide identifier, e.g. '05' or 'A01'.",
        pattern=r"^(A?\d{2,3})$",
    )

    field: str = Field(
        ...,
        description=(
            f"The slide field to update. "
            f"Must be one of: {sorted(_UPDATABLE_FIELDS)}."
        ),
    )

    value: Any = Field(
        ...,
        description=(
            "New value for the field. "
            "Must be compatible with the field's expected type in the Slide schema."
        ),
    )

    @field_validator("field")
    @classmethod
    def _validate_field_name(cls, v: str) -> str:
        if v not in _UPDATABLE_FIELDS:
            raise ValueError(
                f"'{v}' is not an updatable slide field. "
                f"Allowed fields: {sorted(_UPDATABLE_FIELDS)}"
            )
        return v

    @model_validator(mode="after")
    def _validate_metaphor_single_sentence(self) -> "SlideUpdateRequest":
        """When updating the metaphor field, enforce the 1-sentence rule."""
        if self.field == "metaphor" and isinstance(self.value, str):
            _validate_single_sentence(self.value, field_name="metaphor")
        return self

    @model_validator(mode="after")
    def _validate_key_points_max_five(self) -> "SlideUpdateRequest":
        """When updating key_points, enforce the max-5 rule."""
        if self.field == "key_points" and isinstance(self.value, list):
            if len(self.value) > 5:
                raise ValueError(
                    f"key_points must not exceed 5 items; received {len(self.value)}."
                )
        return self


# ─────────────────────────────────────────────────────────────────────────────
# CheckpointApproveRequest
# ─────────────────────────────────────────────────────────────────────────────


class CheckpointApproveRequest(BaseModel):
    """
    Human approves the current pipeline checkpoint and allows the agent to continue.
    """

    session_id: str = Field(
        ...,
        description="Active generation session identifier.",
    )

    checkpoint_id: str = Field(
        ...,
        description="Identifier of the checkpoint being approved.",
    )

    comment: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional free-text comment from the reviewer (e.g., minor notes, praise).",
    )


# ─────────────────────────────────────────────────────────────────────────────
# CheckpointRejectRequest
# ─────────────────────────────────────────────────────────────────────────────


class CheckpointRejectRequest(BaseModel):
    """
    Human rejects the current checkpoint and provides revision instructions.
    The agent pipeline will restart the current stage with the provided feedback.
    """

    session_id: str = Field(
        ...,
        description="Active generation session identifier.",
    )

    checkpoint_id: str = Field(
        ...,
        description="Identifier of the checkpoint being rejected.",
    )

    feedback: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description=(
            "Mandatory revision instructions. "
            "Be specific: 'Slide 3 title must be a conclusion statement, not a topic label.' "
            "The agent will re-run the failed stage with this feedback injected."
        ),
    )

    slide_ids: list[str] | None = Field(
        default=None,
        description=(
            "Optional list of slide IDs the feedback applies to. "
            "When None, feedback is applied to the entire stage output."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GenerateResponse
# ─────────────────────────────────────────────────────────────────────────────


class GenerateResponse(BaseModel):
    """
    Immediate acknowledgement returned when a deck generation request is accepted.

    The actual deck is delivered asynchronously via Server-Sent Events (SSE)
    on the /sessions/{session_id}/stream endpoint.
    """

    session_id: str = Field(
        ...,
        description="Unique identifier for this generation session. Use it to poll or stream progress.",
    )

    status: str = Field(
        default="accepted",
        description="Always 'accepted' for a successful submission.",
    )

    message: str = Field(
        default="Deck generation started. Stream progress at /sessions/{session_id}/stream.",
        description="Human-readable acknowledgement.",
    )

    stream_url: str = Field(
        ...,
        description="Full path to the SSE streaming endpoint for this session.",
    )
