"""
Unit tests for quality_validator.py — the deterministic Python validation engine.

These tests are CRITICAL: they verify the core schema enforcement rules
(metaphor=1 sentence, key_points≤5, evidence≤3, required fields, valid layout/visual types).
"""
import json
import pytest

from agents.quality_validator import validate_deck_data, ALLOWED_LAYOUTS, ALLOWED_VISUAL_TYPES


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_slide(
    slide_id="01",
    section="Setup",
    title="Cloud migration delivers 40% TCO reduction within 18 months",
    objective="Make audience understand the financial case.",
    metaphor="Moving to the cloud is like switching from owning a car to using a taxi service.",
    key_points=None,
    evidence=None,
    layout="two-column",
    visual_type="data-chart",
    takeaway="Migration pays for itself in 18 months.",
) -> dict:
    return {
        "slide_id": slide_id,
        "section": section,
        "title": title,
        "objective": objective,
        "metaphor": metaphor,
        "key_points": key_points or ["Point 1", "Point 2"],
        "evidence": evidence or [{"type": "metric", "detail": "40% reduction", "source": "Gartner"}],
        "visual": {
            "layout": layout,
            "illustration_prompt": {
                "type": visual_type,
                "description": "Cost comparison bar chart",
                "alt_text": "Chart showing 40% savings",
            },
        },
        "takeaway": takeaway,
        "speaker_notes": "Focus on payback period.",
        "assets_needed": [],
    }


def make_deck_json(slides=None, appendix_slides=None) -> str:
    return json.dumps({
        "deck": {
            "title": "Test Deck",
            "type": "Decision Deck",
            "audience": "Executives",
            "tone": "Authoritative",
            "decision_inform_ask": "Decision",
            "context": "Test context",
            "source_material_provided": False,
            "total_slides": 1,
            "slides": slides or [make_slide()],
            "appendix": {
                "slides": appendix_slides or [],
            },
        }
    })


# ── Core validation tests ─────────────────────────────────────────────────────

class TestValidateDeckData:
    def test_valid_deck_passes(self):
        report = validate_deck_data(make_deck_json())
        assert report.valid is True or report.passed is True
        assert len(report.violations) == 0

    def test_invalid_json_returns_error(self):
        report = validate_deck_data("{ invalid json }")
        assert report.valid is False or report.passed is False
        assert any("JSON" in (v.message or v.rule or "") for v in report.violations)

    # ── Metaphor ─────────────────────────────────────────────────────────────

    def test_metaphor_missing_produces_violation(self):
        slide = make_slide(metaphor="")
        report = validate_deck_data(make_deck_json(slides=[slide]))
        assert report.valid is False or report.passed is False
        violation_fields = [v.field for v in report.violations]
        assert "metaphor" in violation_fields

    def test_metaphor_two_sentences_produces_violation(self):
        slide = make_slide(metaphor="First sentence. Second sentence.")
        report = validate_deck_data(make_deck_json(slides=[slide]))
        assert report.valid is False or report.passed is False
        metaphor_violations = [v for v in report.violations if v.field == "metaphor"]
        assert len(metaphor_violations) > 0

    def test_metaphor_one_sentence_passes(self):
        slide = make_slide(metaphor="This is exactly one sentence about the slide.")
        report = validate_deck_data(make_deck_json(slides=[slide]))
        metaphor_violations = [v for v in report.violations if v.field == "metaphor"]
        assert len(metaphor_violations) == 0

    def test_metaphor_with_exclamation_mark_single_sentence_passes(self):
        slide = make_slide(metaphor="Think of this as launching a rocket, not a balloon!")
        report = validate_deck_data(make_deck_json(slides=[slide]))
        metaphor_violations = [v for v in report.violations if v.field == "metaphor"]
        assert len(metaphor_violations) == 0

    # ── key_points ────────────────────────────────────────────────────────────

    def test_key_points_6_items_produces_violation(self):
        slide = make_slide(key_points=["1", "2", "3", "4", "5", "6"])
        report = validate_deck_data(make_deck_json(slides=[slide]))
        assert report.valid is False or report.passed is False
        kp_violations = [v for v in report.violations if v.field == "key_points"]
        assert len(kp_violations) > 0

    def test_key_points_5_items_passes(self):
        slide = make_slide(key_points=["1", "2", "3", "4", "5"])
        report = validate_deck_data(make_deck_json(slides=[slide]))
        kp_violations = [v for v in report.violations if v.field == "key_points"]
        assert len(kp_violations) == 0

    def test_key_points_empty_list_passes(self):
        slide = make_slide(key_points=[])
        report = validate_deck_data(make_deck_json(slides=[slide]))
        kp_violations = [v for v in report.violations if v.field == "key_points"]
        assert len(kp_violations) == 0

    # ── evidence ─────────────────────────────────────────────────────────────

    def test_evidence_4_items_produces_violation(self):
        slide = make_slide(evidence=[
            {"type": "metric", "detail": "A"},
            {"type": "metric", "detail": "B"},
            {"type": "metric", "detail": "C"},
            {"type": "metric", "detail": "D"},
        ])
        report = validate_deck_data(make_deck_json(slides=[slide]))
        assert report.valid is False or report.passed is False
        ev_violations = [v for v in report.violations if v.field == "evidence"]
        assert len(ev_violations) > 0

    def test_evidence_3_items_passes(self):
        slide = make_slide(evidence=[
            {"type": "metric", "detail": "A"},
            {"type": "quote", "detail": "B"},
            {"type": "benchmark", "detail": "C"},
        ])
        report = validate_deck_data(make_deck_json(slides=[slide]))
        ev_violations = [v for v in report.violations if v.field == "evidence"]
        assert len(ev_violations) == 0

    # ── Required fields ───────────────────────────────────────────────────────

    def test_empty_title_produces_violation(self):
        slide = make_slide(title="")
        report = validate_deck_data(make_deck_json(slides=[slide]))
        title_violations = [v for v in report.violations if v.field == "title"]
        assert len(title_violations) > 0

    def test_empty_section_produces_violation(self):
        slide = make_slide(section="")
        report = validate_deck_data(make_deck_json(slides=[slide]))
        section_violations = [v for v in report.violations if v.field == "section"]
        assert len(section_violations) > 0

    # ── Layout validation ─────────────────────────────────────────────────────

    def test_invalid_layout_produces_violation(self):
        slide = make_slide(layout="invalid-layout")
        report = validate_deck_data(make_deck_json(slides=[slide]))
        layout_violations = [v for v in report.violations if "layout" in v.field]
        assert len(layout_violations) > 0

    def test_all_8_layouts_pass(self):
        for layout in ALLOWED_LAYOUTS:
            slide = make_slide(layout=layout)
            report = validate_deck_data(make_deck_json(slides=[slide]))
            layout_violations = [v for v in report.violations if "layout" in v.field]
            assert len(layout_violations) == 0, f"Layout '{layout}' incorrectly rejected"

    # ── Visual type validation ────────────────────────────────────────────────

    def test_invalid_visual_type_produces_violation(self):
        slide = make_slide(visual_type="invalid-type")
        report = validate_deck_data(make_deck_json(slides=[slide]))
        vt_violations = [v for v in report.violations if "illustration_prompt" in v.field]
        assert len(vt_violations) > 0

    def test_all_8_visual_types_pass(self):
        for vtype in ALLOWED_VISUAL_TYPES:
            slide = make_slide(visual_type=vtype)
            report = validate_deck_data(make_deck_json(slides=[slide]))
            vt_violations = [v for v in report.violations if "illustration_prompt" in v.field]
            assert len(vt_violations) == 0, f"Visual type '{vtype}' incorrectly rejected"

    # ── Appendix slides ───────────────────────────────────────────────────────

    def test_appendix_slides_also_validated(self):
        appendix_slide = make_slide(slide_id="A01", section="Appendix", metaphor="First sentence. Second sentence.")
        report = validate_deck_data(make_deck_json(appendix_slides=[appendix_slide]))
        metaphor_violations = [v for v in report.violations if v.field == "metaphor" and v.slide_id == "A01"]
        assert len(metaphor_violations) > 0

    def test_slides_checked_count(self):
        report = validate_deck_data(make_deck_json(slides=[make_slide("01"), make_slide("02")]))
        assert report.slides_checked == 2 or report.total_slides_checked == 2

    # ── Multiple violations ───────────────────────────────────────────────────

    def test_multiple_violations_collected(self):
        slide = make_slide(
            metaphor="First. Second.",
            key_points=["1", "2", "3", "4", "5", "6"],
            title="",
        )
        report = validate_deck_data(make_deck_json(slides=[slide]))
        assert len(report.violations) >= 3
