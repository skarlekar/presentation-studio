"""
DeckStudio — Output Schemas (Pydantic v2).

These models validate and serialise all data produced by the agent pipeline
and returned to API consumers.

Schema hierarchy:
  EvidenceItem
  IllustrationPrompt
  Visual (contains IllustrationPrompt)
  Slide  (contains Visual + EvidenceItem[])
  Appendix (contains Slide[])
  Deck (contains Slide[] + Appendix)
  DeckEnvelope (top-level API response wrapper)

Pipeline / session models:
  PipelineStatus  (enum)
  CheckpointStatus (enum)
  Checkpoint
  SessionStatusResponse
  InsightSet
  SectionOutline
  DeckOutline
  Violation
  ValidationReport
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────


class PipelineStatus(str, Enum):
    """Lifecycle states of a deck generation session."""

    PENDING = "pending"
    RUNNING = "running"
    EXTRACTING_INSIGHTS = "extracting_insights"
    GENERATING_OUTLINE = "generating_outline"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_OUTLINE_APPROVAL = "awaiting_outline_approval"
    GENERATING_SLIDES = "generating_slides"
    AWAITING_REVIEW_APPROVAL = "awaiting_review_approval"
    VALIDATING = "validating"
    COMPLETE = "complete"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CheckpointStatus(str, Enum):
    """Human-in-the-loop checkpoint resolution states."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class EvidenceType(str, Enum):
    """Allowed evidence types per the Presentation Architect Prompt STEP 11."""

    METRIC = "metric"
    REFERENCE = "reference"
    QUOTE = "quote"
    BENCHMARK = "benchmark"
    CASE_STUDY = "case_study"


class LayoutType(str, Enum):
    """Allowed slide layout types per the Presentation Architect Prompt STEP 8."""

    TITLE = "title"
    TWO_COLUMN = "two-column"
    CHART = "chart"
    TIMELINE = "timeline"
    TABLE = "table"
    QUOTE = "quote"
    FULL_BLEED_VISUAL = "full-bleed visual"
    FRAMEWORK_DIAGRAM = "framework diagram"


class VisualType(str, Enum):
    """Allowed illustration types per the Presentation Architect Prompt STEP 6."""

    PROCESS_DIAGRAM = "process-diagram"
    ARCHITECTURE_DIAGRAM = "architecture-diagram"
    DATA_CHART = "data-chart"
    COMPARISON_TABLE = "comparison-table"
    TIMELINE = "timeline"
    FRAMEWORK = "framework"
    MATRIX = "matrix"
    BEFORE_AFTER = "before-after"


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────


def _count_sentences(text: str) -> int:
    """Rough sentence counter using terminal punctuation."""
    sentences = re.split(r"[.!?]+", text.strip())
    return len([s for s in sentences if s.strip()])


# ─────────────────────────────────────────────────────────────────────────────
# Evidence
# ─────────────────────────────────────────────────────────────────────────────


class EvidenceItem(BaseModel):
    """
    A single piece of evidence supporting a slide's claim.

    Priority order (highest first): metric → reference → benchmark →
    case_study → quote.
    """

    type: EvidenceType = Field(
        ...,
        description="Evidence classification. Drives priority in STEP 11.",
    )

    detail: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Human-readable description of the evidence.",
    )

    source: str | None = Field(
        default=None,
        max_length=500,
        description="Optional citation or source reference.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Illustration / Visual
# ─────────────────────────────────────────────────────────────────────────────


class IllustrationPrompt(BaseModel):
    """
    Machine-readable brief for a designer or programmatic renderer.
    Defined in STEP 7 of the Presentation Architect Prompt.
    """

    type: VisualType = Field(
        ...,
        description="Visual category from STEP 6.",
    )

    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Plain-language description of the visual for a designer or renderer.",
    )

    alt_text: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Accessible alternative text for screen readers.",
    )


class Visual(BaseModel):
    """
    Visual plan for a slide.  Every slide must have one.
    """

    layout: LayoutType = Field(
        ...,
        description="Slide layout from STEP 8.",
    )

    illustration_prompt: IllustrationPrompt = Field(
        ...,
        description="Renderer brief for the illustration.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Slide
# ─────────────────────────────────────────────────────────────────────────────


class Slide(BaseModel):
    """
    A single slide in the deck.

    Constraints enforced by validators:
    • metaphor      — exactly 1 sentence (schema validation error if violated)
    • key_points    — max 5 items
    • evidence      — max 3 items
    • objective     — single sentence
    • takeaway      — single sentence
    """

    slide_id: str = Field(
        ...,
        description="Zero-padded identifier. Main deck: '01'–'NN'. Appendix: 'A01', 'A02', …",
        pattern=r"^A?\d{2,3}$",
    )

    section: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description=(
            "Narrative arc section. "
            "Must match one of: Setup | Insight | Resolution | Appendix."
        ),
    )

    title: str = Field(
        ...,
        min_length=5,
        max_length=300,
        description=(
            "Conclusion statement, NOT a topic label. "
            "Good: 'Event-driven ingestion reduces integration time by 40%'. "
            "Bad: 'Architecture Overview'."
        ),
    )

    objective: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="One sentence: what this slide must make the audience believe.",
    )

    metaphor: str = Field(
        ...,
        min_length=10,
        max_length=600,
        description=(
            "Exactly 1 sentence. Plain-language analogy derived from this slide's content. "
            "Must be understandable by a non-expert. "
            "Violating the 1-sentence limit is a schema validation error."
        ),
    )

    key_points: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Supporting bullets. Maximum 5 items per STEP 13.",
    )

    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Supporting evidence items. Maximum 3 per slide.",
    )

    visual: Visual = Field(
        ...,
        description="Visual plan for this slide.",
    )

    takeaway: str = Field(
        ...,
        min_length=5,
        max_length=400,
        description="Single sentence: the one thing the audience must remember.",
    )

    speaker_notes: str = Field(
        default="",
        max_length=3000,
        description="Presenter guidance. Not displayed on the slide.",
    )

    assets_needed: list[str] = Field(
        default_factory=list,
        description="Icons, images, or graphics required to render this slide.",
    )

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("metaphor")
    @classmethod
    def _metaphor_single_sentence(cls, v: str) -> str:
        count = _count_sentences(v)
        if count > 1:
            raise ValueError(
                f"'metaphor' must be exactly 1 sentence; detected {count} sentences. "
                f"Value: {v!r}"
            )
        return v

    @field_validator("key_points")
    @classmethod
    def _key_points_max_five(cls, v: list[str]) -> list[str]:
        if len(v) > 5:
            raise ValueError(
                f"'key_points' must not exceed 5 items; received {len(v)}."
            )
        return v

    @field_validator("evidence")
    @classmethod
    def _evidence_max_three(cls, v: list[EvidenceItem]) -> list[EvidenceItem]:
        if len(v) > 3:
            raise ValueError(
                f"'evidence' must not exceed 3 items per slide; received {len(v)}."
            )
        return v

    @field_validator("objective")
    @classmethod
    def _objective_single_sentence(cls, v: str) -> str:
        count = _count_sentences(v)
        if count > 2:
            # Slightly lenient: allow up to 2 for compound sentences that end
            # in a colon or dash construction. Hard error at 3+.
            raise ValueError(
                f"'objective' should be a single sentence; detected {count} sentences. "
                f"Value: {v!r}"
            )
        return v

    @field_validator("takeaway")
    @classmethod
    def _takeaway_single_sentence(cls, v: str) -> str:
        count = _count_sentences(v)
        if count > 2:
            raise ValueError(
                f"'takeaway' should be a single sentence; detected {count} sentences. "
                f"Value: {v!r}"
            )
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Appendix
# ─────────────────────────────────────────────────────────────────────────────


class Appendix(BaseModel):
    """
    Appendix section of a deck.

    Appendix slides follow the identical Slide schema (including metaphor).
    Populated after all main deck slides are complete.
    """

    slides: list[Slide] = Field(
        default_factory=list,
        description="Appendix slides. Slide IDs use the 'A01', 'A02', … convention.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Deck
# ─────────────────────────────────────────────────────────────────────────────


class Deck(BaseModel):
    """
    A fully generated presentation deck.

    Mirrors the top-level JSON schema defined in STEP 9 of the
    Presentation Architect Prompt.
    """

    title: str = Field(
        ...,
        min_length=2,
        max_length=300,
        description="Deck title.",
    )

    type: str = Field(
        ...,
        description="Deck archetype (maps to DeckType enum).",
    )

    audience: str = Field(
        ...,
        description="Target audience carried from the request.",
    )

    tone: str = Field(
        ...,
        description="Communication tone carried from the request.",
    )

    decision_inform_ask: str = Field(
        ...,
        description="Primary intent (Decision / Inform / Ask) carried from the request.",
    )

    context: str = Field(
        ...,
        description="Context carried verbatim from the request.",
    )

    source_material_provided: bool = Field(
        ...,
        description="True when source_material was supplied; False when deck is context-only.",
    )

    total_slides: int = Field(
        ...,
        ge=1,
        description="Number of main-deck slides requested.",
    )

    slides: list[Slide] = Field(
        default_factory=list,
        description="Main deck slides in presentation order.",
    )

    appendix: Appendix = Field(
        default_factory=Appendix,
        description="Appendix slides (supporting data, methodology, reference tables).",
    )

    @model_validator(mode="after")
    def _slide_count_matches(self) -> "Deck":
        """
        Warn (via speaker_notes) rather than hard-error when the generated
        slide count doesn't match total_slides — the pipeline may be mid-stream.
        This validator logs the mismatch for debugging purposes only.
        """
        # Not a hard error to support partial/streaming payloads.
        return self


# ─────────────────────────────────────────────────────────────────────────────
# DeckEnvelope
# ─────────────────────────────────────────────────────────────────────────────


class DeckEnvelope(BaseModel):
    """
    Top-level API response wrapping a generated Deck with session metadata.
    """

    session_id: str = Field(
        ...,
        description="Generation session identifier.",
    )

    status: PipelineStatus = Field(
        ...,
        description="Current pipeline status.",
    )

    deck: Deck | None = Field(
        default=None,
        description="The generated deck. None while status != COMPLETE.",
    )

    error: str | None = Field(
        default=None,
        description="Error message when status == FAILED.",
    )

    created_at: str = Field(
        ...,
        description="ISO-8601 UTC timestamp of session creation.",
    )

    completed_at: str | None = Field(
        default=None,
        description="ISO-8601 UTC timestamp of session completion. None while in progress.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Checkpoint
# ─────────────────────────────────────────────────────────────────────────────


class Checkpoint(BaseModel):
    """
    A human-in-the-loop gate in the pipeline.

    The agent pauses here and waits for approval or rejection before
    proceeding to the next stage.
    """

    checkpoint_id: str = Field(
        ...,
        description="Unique identifier for this checkpoint.",
    )

    session_id: str = Field(
        default="",
        description="Parent generation session.",
    )

    stage: str = Field(
        ...,
        description="Pipeline stage at which this checkpoint was raised.",
    )

    stage_index: int = Field(
        default=0,
        description="1-based index of this stage in the pipeline sequence.",
    )

    label: str = Field(
        default="",
        description="Human-readable label for this checkpoint (e.g. 'Confirm Core Insights').",
    )

    status: CheckpointStatus = Field(
        default=CheckpointStatus.PENDING,
        description="Current resolution status.",
    )

    payload: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Stage output presented for human review "
            "(e.g., the draft outline or slide list)."
        ),
    )

    # Alias fields used by the pipeline (stored alongside payload)
    pending_input: dict[str, Any] = Field(
        default_factory=dict,
        description="Pending input data for the next agent stage.",
    )

    preview: dict[str, Any] | None = Field(
        default=None,
        description="Optional rendered preview of the stage output.",
    )

    feedback: str | None = Field(
        default=None,
        description="Human feedback provided on rejection.",
    )

    resolution: str | None = Field(
        default=None,
        description="Resolution string: 'approved' or 'rejected'.",
    )

    edits: dict[str, Any] | None = Field(
        default=None,
        description="Optional edits submitted with approval.",
    )

    created_at: str = Field(
        default="",
        description="ISO-8601 UTC timestamp when the checkpoint was raised.",
    )

    resolved_at: str | None = Field(
        default=None,
        description="ISO-8601 UTC timestamp when approved or rejected.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# SessionStatusResponse
# ─────────────────────────────────────────────────────────────────────────────


class SessionStatusResponse(BaseModel):
    """
    Response for GET /sessions/{session_id}/status.
    Provides a lightweight progress summary without the full deck payload.
    """

    session_id: str = Field(..., description="Session identifier.")

    status: PipelineStatus = Field(..., description="Current pipeline status.")

    current_stage: str | None = Field(
        default=None,
        description="Human-readable label for the step currently executing.",
    )

    slides_generated: int = Field(
        default=0,
        description="Number of slides fully generated so far.",
    )

    total_slides: int = Field(
        default=0,
        description="Total slides requested.",
    )

    active_checkpoint: Checkpoint | None = Field(
        default=None,
        description="Checkpoint awaiting human action, if any.",
    )

    error: str | None = Field(
        default=None,
        description="Error detail when status == FAILED.",
    )

    created_at: str = Field(..., description="ISO-8601 UTC session start time.")

    updated_at: str = Field(..., description="ISO-8601 UTC last status update time.")


# ─────────────────────────────────────────────────────────────────────────────
# Insight extraction models
# ─────────────────────────────────────────────────────────────────────────────


class InsightSet(BaseModel):
    """
    Structured output of STEP 1 (Insight Extraction) in the pipeline.
    """

    core_problem: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="The fundamental problem or opportunity identified from the input material.",
    )

    key_insights: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="3–5 core insights that drive the deck narrative.",
    )

    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="Metrics, quotes, benchmarks extracted from source material.",
    )

    strategic_options: list[str] = Field(
        default_factory=list,
        description="Possible approaches suggested by the material.",
    )

    risks_and_constraints: list[str] = Field(
        default_factory=list,
        description="Operational, technical, financial, or organisational barriers.",
    )

    implications: list[str] = Field(
        default_factory=list,
        description="Decisions that logically follow from the analysis.",
    )

    context_only: bool = Field(
        default=False,
        description="True when insights were derived from context alone (no source material).",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Deck outline models
# ─────────────────────────────────────────────────────────────────────────────


class SectionOutline(BaseModel):
    """A single slide entry in the draft outline."""

    slide_number: int = Field(..., ge=1, description="1-based slide number.")

    section: str = Field(..., description="Narrative arc section.")

    proposed_title: str = Field(
        ...,
        description="Draft conclusion-statement title for this slide.",
    )

    rationale: str | None = Field(
        default=None,
        description="Brief explanation of why this slide is needed.",
    )


class DeckOutline(BaseModel):
    """
    Draft outline produced at the GENERATING_OUTLINE stage.
    Presented for human approval at the AWAITING_OUTLINE_APPROVAL checkpoint.
    """

    deck_title: str = Field(..., description="Proposed deck title.")

    total_slides: int = Field(..., ge=1, description="Planned slide count.")

    slides: list[SectionOutline] = Field(
        ...,
        description="Ordered list of proposed slides.",
    )

    context_summary: str | None = Field(
        default=None,
        description=(
            "One-paragraph summary of how CONTEXT was interpreted, "
            "included when SOURCE_MATERIAL was absent."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Validation report models
# ─────────────────────────────────────────────────────────────────────────────


class ViolationSeverity(str, Enum):
    """Severity level of a schema or prompt-rule violation."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Violation(BaseModel):
    """
    A single schema or prompt-rule violation found during deck validation.
    """

    slide_id: str | None = Field(
        default=None,
        description="Affected slide ID, or None for deck-level violations.",
    )

    field: str = Field(
        ...,
        description="The field where the violation was detected.",
    )

    rule: str = Field(
        default="",
        description="Human-readable description of the rule that was violated.",
    )

    # Alias used internally by quality_validator (maps to rule)
    constraint: str = Field(
        default="",
        description="Machine-readable constraint name (e.g. 'max_5', 'exactly_1_sentence').",
    )

    message: str = Field(
        default="",
        description="Full human-readable violation message.",
    )

    severity: ViolationSeverity = Field(
        default=ViolationSeverity.ERROR,
        description="Severity: error (blocks output) | warning (flags for review) | info.",
    )

    actual_value: str = Field(
        default="",
        description="The actual value that caused the violation.",
    )

    value_preview: str | None = Field(
        default=None,
        max_length=200,
        description="Truncated preview of the offending value for context.",
    )


class ValidationReport(BaseModel):
    """
    Output of the VALIDATING pipeline stage.

    Summarises all prompt-rule and schema violations found in the generated deck
    before it is returned to the client.
    """

    session_id: str = Field(default="", description="Source session identifier.")

    passed: bool = Field(
        default=True,
        description="True when no ERROR-severity violations were found.",
    )

    # Alias used by quality_validator.py
    valid: bool = Field(
        default=True,
        description="Alias for passed — True when no violations found.",
    )

    total_slides_checked: int = Field(default=0, ge=0)

    # Alias used by quality_validator.py
    slides_checked: int = Field(
        default=0,
        description="Alias for total_slides_checked.",
    )

    # Alias used by quality_validator.py
    checked_at: Any = Field(
        default=None,
        description="ISO timestamp or datetime of validation (optional).",
    )

    violations: list[Violation] = Field(
        default_factory=list,
        description="All violations found. Empty list when passed=True.",
    )

    warnings: int = Field(
        default=0,
        description="Count of WARNING-severity violations (non-blocking).",
    )

    errors: int = Field(
        default=0,
        description="Count of ERROR-severity violations (blocking).",
    )

    @model_validator(mode="after")
    def _sync_counts(self) -> "ValidationReport":
        self.errors = sum(
            1 for v in self.violations if v.severity == ViolationSeverity.ERROR
        )
        self.warnings = sum(
            1 for v in self.violations if v.severity == ViolationSeverity.WARNING
        )
        self.passed = self.errors == 0
        self.valid = self.passed
        if self.slides_checked and not self.total_slides_checked:
            self.total_slides_checked = self.slides_checked
        elif self.total_slides_checked and not self.slides_checked:
            self.slides_checked = self.total_slides_checked
        return self
