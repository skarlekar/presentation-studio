"""
Unit tests for Pydantic schemas — input.py and output.py.
"""
import pytest
from pydantic import ValidationError

from schemas.input import (
    DeckRequest, DeckType, DecisionInformAsk,
    CheckpointApproveRequest, CheckpointRejectRequest, SlideUpdateRequest,
)
from schemas.output import (
    Slide, EvidenceItem, EvidenceType, LayoutType, VisualType,
    IllustrationPrompt, Visual, Violation, ValidationReport,
    ViolationSeverity,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def valid_slide(**overrides) -> dict:
    base = {
        "slide_id": "01",
        "section": "Setup",
        "title": "Migration reduces TCO by 40% within 18 months",
        "objective": "Make the audience understand the financial case.",
        "metaphor": "Moving to the cloud is like switching from owning a car to using a taxi.",
        "key_points": ["Point 1", "Point 2"],
        "evidence": [
            {"type": "metric", "detail": "40% reduction per Gartner 2024"}
        ],
        "visual": {
            "layout": "two-column",
            "illustration_prompt": {
                "type": "data-chart",
                "description": "Bar chart comparing costs",
                "alt_text": "Cost comparison chart",
            },
        },
        "takeaway": "The migration pays for itself in 18 months.",
        "speaker_notes": "Emphasize payback period.",
        "assets_needed": [],
    }
    base.update(overrides)
    return base


def valid_deck_request(**overrides) -> dict:
    base = {
        "context": "We need to build a cloud migration business case.",
        "number_of_slides": 11,
        "audience": "C-suite executives",
        "deck_type": "Decision Deck",
        "decision_inform_ask": "Decision",
        "tone": "Authoritative and data-driven",
    }
    base.update(overrides)
    return base


# ── DeckRequest tests ─────────────────────────────────────────────────────────

class TestDeckRequest:
    def test_valid_request(self):
        req = DeckRequest(**valid_deck_request())
        assert req.number_of_slides == 11
        assert req.deck_type == DeckType.DECISION

    def test_requires_context_or_source_material(self):
        with pytest.raises(ValidationError, match="At least one of"):
            DeckRequest(
                context=None,
                source_material=None,
                number_of_slides=11,
                audience="C-suite",
                deck_type="Decision Deck",
                decision_inform_ask="Decision",
                tone="Authoritative",
            )

    def test_source_material_alone_is_valid(self):
        req = DeckRequest(
            source_material="Document content here",
            number_of_slides=11,
            audience="C-suite",
            deck_type="Decision Deck",
            decision_inform_ask="Decision",
            tone="Authoritative",
        )
        assert req.source_material == "Document content here"
        assert req.context is None

    def test_number_of_slides_min_3(self):
        with pytest.raises(ValidationError):
            DeckRequest(**valid_deck_request(number_of_slides=2))

    def test_number_of_slides_max_60(self):
        with pytest.raises(ValidationError):
            DeckRequest(**valid_deck_request(number_of_slides=61))

    def test_number_of_slides_boundary_3(self):
        req = DeckRequest(**valid_deck_request(number_of_slides=3))
        assert req.number_of_slides == 3

    def test_number_of_slides_boundary_60(self):
        req = DeckRequest(**valid_deck_request(number_of_slides=60))
        assert req.number_of_slides == 60

    def test_blank_context_treated_as_none(self):
        req = DeckRequest(**valid_deck_request(context="   ", source_material="Some content"))
        assert req.context is None

    def test_all_deck_types_accepted(self):
        for dt in DeckType:
            req = DeckRequest(**valid_deck_request(deck_type=dt))
            assert req.deck_type == dt

    def test_all_dia_options_accepted(self):
        for dia in DecisionInformAsk:
            req = DeckRequest(**valid_deck_request(decision_inform_ask=dia))
            assert req.decision_inform_ask == dia


# ── Slide schema tests ────────────────────────────────────────────────────────

class TestSlideSchema:
    def test_valid_slide(self):
        slide = Slide(**valid_slide())
        assert slide.slide_id == "01"
        assert slide.metaphor.startswith("Moving")

    def test_metaphor_multi_sentence_raises(self):
        """Metaphor must be exactly 1 sentence — the MOST CRITICAL schema constraint."""
        with pytest.raises(ValidationError, match="1 sentence"):
            Slide(**valid_slide(
                metaphor="First sentence. Second sentence."
            ))

    def test_metaphor_single_sentence_ok(self):
        slide = Slide(**valid_slide(
            metaphor="This is exactly one sentence."
        ))
        assert slide.metaphor == "This is exactly one sentence."

    def test_key_points_max_5(self):
        with pytest.raises(ValidationError, match="5"):
            Slide(**valid_slide(
                key_points=["1", "2", "3", "4", "5", "6"]
            ))

    def test_key_points_5_is_ok(self):
        slide = Slide(**valid_slide(
            key_points=["1", "2", "3", "4", "5"]
        ))
        assert len(slide.key_points) == 5

    def test_evidence_max_3(self):
        with pytest.raises(ValidationError, match="3"):
            Slide(**valid_slide(
                evidence=[
                    {"type": "metric", "detail": "Detail item A"},
                    {"type": "metric", "detail": "B"},
                    {"type": "metric", "detail": "C"},
                    {"type": "metric", "detail": "D"},  # 4th — should fail
                ]
            ))

    def test_evidence_3_is_ok(self):
        slide = Slide(**valid_slide(
            evidence=[
                {"type": "metric", "detail": "Detail item A"},
                {"type": "quote", "detail": "Detail item B"},
                {"type": "benchmark", "detail": "Detail item C"},
            ]
        ))
        assert len(slide.evidence) == 3

    def test_appendix_slide_id_pattern(self):
        slide = Slide(**valid_slide(slide_id="A01", section="Appendix"))
        assert slide.slide_id == "A01"

    def test_invalid_layout_rejected(self):
        with pytest.raises(ValidationError):
            Slide(**valid_slide(visual={
                "layout": "invalid-layout",
                "illustration_prompt": {
                    "type": "data-chart",
                    "description": "Description of the visual element",
                    "alt_text": "Alt text description",
                },
            }))

    def test_invalid_visual_type_rejected(self):
        with pytest.raises(ValidationError):
            Slide(**valid_slide(visual={
                "layout": "two-column",
                "illustration_prompt": {
                    "type": "invalid-type",
                    "description": "Description of the visual element",
                    "alt_text": "Alt text description",
                },
            }))

    def test_all_8_layouts_accepted(self):
        for layout in LayoutType:
            slide = Slide(**valid_slide(visual={
                "layout": layout,
                "illustration_prompt": {
                    "type": "data-chart",
                    "description": "Description of the visual element",
                    "alt_text": "Alt text description",
                },
            }))
            assert slide.visual.layout == layout

    def test_all_8_visual_types_accepted(self):
        for vtype in VisualType:
            slide = Slide(**valid_slide(visual={
                "layout": "two-column",
                "illustration_prompt": {
                    "type": vtype,
                    "description": "Description of the visual element",
                    "alt_text": "Alt text description",
                },
            }))
            assert slide.visual.illustration_prompt.type == vtype


# ── ValidationReport tests ────────────────────────────────────────────────────

class TestValidationReport:
    def test_passed_when_no_violations(self):
        report = ValidationReport(total_slides_checked=5, violations=[])
        assert report.passed is True
        assert report.errors == 0

    def test_failed_when_error_violations(self):
        v = Violation(field="metaphor", rule="exactly_1_sentence", severity=ViolationSeverity.ERROR)
        report = ValidationReport(total_slides_checked=5, violations=[v])
        assert report.passed is False
        assert report.errors == 1

    def test_warning_does_not_fail(self):
        v = Violation(field="speaker_notes", rule="recommended", severity=ViolationSeverity.WARNING)
        report = ValidationReport(total_slides_checked=5, violations=[v])
        assert report.passed is True
        assert report.warnings == 1
        assert report.errors == 0


# ── CheckpointApproveRequest tests ───────────────────────────────────────────

class TestCheckpointApproveRequest:
    def test_valid_approve(self):
        req = CheckpointApproveRequest(
            session_id="sess-001",
            checkpoint_id="cp-001",
            comment="Looks good",
        )
        assert req.comment == "Looks good"

    def test_edits_field_optional(self):
        req = CheckpointApproveRequest()
        assert req.edits is None


# ── CheckpointRejectRequest tests ────────────────────────────────────────────

class TestCheckpointRejectRequest:
    def test_feedback_required(self):
        with pytest.raises(ValidationError):
            CheckpointRejectRequest(session_id="s", checkpoint_id="c")

    def test_feedback_min_length(self):
        with pytest.raises(ValidationError):
            CheckpointRejectRequest(
                session_id="s", checkpoint_id="c", feedback="short"
            )

    def test_valid_reject(self):
        req = CheckpointRejectRequest(
            session_id="s",
            checkpoint_id="c",
            feedback="Slide titles must be conclusion statements, not topic labels.",
        )
        assert req.feedback.startswith("Slide titles")
