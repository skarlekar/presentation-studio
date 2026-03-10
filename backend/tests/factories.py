"""
DeckStudio test factories.

Uses factory_boy + Faker to generate valid, randomised instances of all
schema classes.  All factories produce Pydantic model instances directly
(not ORM objects) via the ``_meta.model`` / custom ``_create`` pattern.

Factory inventory:
  EvidenceItemFactory
  IllustrationPromptFactory
  VisualFactory
  SlideFactory
  AppendixFactory
  DeckFactory
  DeckEnvelopeFactory
  DeckRequestFactory

Usage:
    from tests.factories import SlideFactory, DeckRequestFactory

    slide = SlideFactory()                          # random valid Slide
    slide = SlideFactory(slide_id="03")             # override one field
    deck_req = DeckRequestFactory(number_of_slides=5)
    batch = SlideFactory.build_batch(3)
"""
from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from typing import Any

import factory
from faker import Faker

from schemas.input import DeckRequest, DeckType, DecisionInformAsk
from schemas.output import (
    Appendix,
    Deck,
    DeckEnvelope,
    EvidenceItem,
    EvidenceType,
    IllustrationPrompt,
    LayoutType,
    PipelineStatus,
    Slide,
    Visual,
    VisualType,
)

fake = Faker()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _random_slide_id(is_appendix: bool = False) -> str:
    n = random.randint(1, 30)
    prefix = "A" if is_appendix else ""
    return f"{prefix}{n:02d}"


def _single_sentence_metaphor() -> str:
    """
    Generate a one-sentence plain-language metaphor using everyday language.
    Ensures we stay under the 1-sentence validation limit.
    """
    templates = [
        "Running this system without a unified plan is like trying to bake a cake without knowing how many eggs you have.",
        "Adopting this approach is like switching from individual car trips to a well-timed bus route — everyone arrives faster at lower cost.",
        "Ignoring this risk is like skipping the weather forecast before a camping trip: avoidable surprises become expensive lessons.",
        "This recommendation is like upgrading from hand-written sticky notes to a shared calendar — everyone stays in sync automatically.",
        "Delaying action here is like waiting until the check engine light turns red before visiting a mechanic.",
        "The current fragmentation is like having ten different TV remotes when one universal remote would do the job.",
        "Our integration overhead is like paying a full-time translator for every conversation instead of agreeing on one common language.",
        "This investment is like insulating your home: upfront cost, but lower bills every month forever after.",
        "Choosing the right architecture here is like picking the right foundation before building a house — everything else depends on it.",
        "Phasing the rollout is like learning to drive in an empty car park before merging onto the motorway.",
    ]
    return random.choice(templates)


# ─────────────────────────────────────────────────────────────────────────────
# Base Pydantic factory mixin
# ─────────────────────────────────────────────────────────────────────────────


class PydanticFactory(factory.Factory):
    """
    Base factory that instantiates Pydantic models instead of plain dicts.

    Subclasses must set ``Meta.model`` to a Pydantic BaseModel class.
    factory_boy's default ``_create`` passes kwargs to the constructor,
    which is exactly what Pydantic expects.
    """

    class Meta:
        abstract = True

    @classmethod
    def _create(cls, model_class: type, *args: Any, **kwargs: Any) -> Any:
        return model_class(**kwargs)

    @classmethod
    def _build(cls, model_class: type, *args: Any, **kwargs: Any) -> Any:
        return model_class(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# EvidenceItemFactory
# ─────────────────────────────────────────────────────────────────────────────


class EvidenceItemFactory(PydanticFactory):
    """Generates a valid EvidenceItem."""

    class Meta:
        model = EvidenceItem

    type = factory.LazyFunction(lambda: random.choice(list(EvidenceType)))
    detail = factory.LazyFunction(
        lambda: fake.sentence(nb_words=random.randint(8, 20)).rstrip(".")
    )
    source = factory.LazyFunction(
        lambda: fake.company() + " " + str(random.randint(2020, 2025)) if random.random() > 0.3 else None
    )


# ─────────────────────────────────────────────────────────────────────────────
# IllustrationPromptFactory
# ─────────────────────────────────────────────────────────────────────────────


class IllustrationPromptFactory(PydanticFactory):
    """Generates a valid IllustrationPrompt."""

    class Meta:
        model = IllustrationPrompt

    type = factory.LazyFunction(lambda: random.choice(list(VisualType)))
    description = factory.LazyFunction(
        lambda: (
            "A " + random.choice([
                "process flow diagram showing the four steps from intake to delivery.",
                "bar chart comparing current-state costs against projected future-state costs.",
                "architecture diagram with three layers: ingestion, processing, and consumption.",
                "2x2 matrix with risk on the x-axis and impact on the y-axis.",
                "timeline showing six milestones across an 18-month delivery roadmap.",
                "before/after comparison of system architecture, split vertically.",
                "framework pyramid illustrating strategic, tactical, and operational layers.",
                "comparison table with three options across five evaluation criteria.",
            ])
        )
    )
    alt_text = factory.LazyFunction(
        lambda: fake.sentence(nb_words=10).rstrip(".")
    )


# ─────────────────────────────────────────────────────────────────────────────
# VisualFactory
# ─────────────────────────────────────────────────────────────────────────────


class VisualFactory(PydanticFactory):
    """Generates a valid Visual (layout + illustration_prompt)."""

    class Meta:
        model = Visual

    layout = factory.LazyFunction(lambda: random.choice(list(LayoutType)))
    illustration_prompt = factory.SubFactory(IllustrationPromptFactory)


# ─────────────────────────────────────────────────────────────────────────────
# SlideFactory
# ─────────────────────────────────────────────────────────────────────────────


_SECTIONS = ["Setup", "Insight", "Resolution"]

_CONCLUSION_TITLES = [
    "Event-driven ingestion reduces integration time by 40%",
    "Fragmented data ownership is costing us $2M annually in rework",
    "A unified data platform eliminates 80% of cross-team dependencies",
    "Phased migration reduces delivery risk by two-thirds",
    "Cloud-native infrastructure cuts operational costs by 35% over three years",
    "Real-time data access enables same-day decision-making instead of weekly reports",
    "The proposed architecture passes all regulatory compliance requirements",
    "Executive alignment on this decision prevents a $5M budget overrun",
    "Automated testing reduces post-release defects by 60%",
    "Investing now avoids a $12M platform rewrite in 18 months",
]


class SlideFactory(PydanticFactory):
    """
    Generates a valid Slide conforming to all schema constraints:
    • metaphor: exactly 1 sentence
    • key_points: ≤ 5 items
    • evidence: ≤ 3 items
    """

    class Meta:
        model = Slide

    slide_id = factory.LazyFunction(lambda: _random_slide_id())
    section = factory.LazyFunction(lambda: random.choice(_SECTIONS))
    title = factory.LazyFunction(lambda: random.choice(_CONCLUSION_TITLES))
    objective = factory.LazyFunction(
        lambda: fake.sentence(nb_words=random.randint(10, 20)).rstrip(".")
        + "."
    )
    metaphor = factory.LazyFunction(_single_sentence_metaphor)
    key_points = factory.LazyFunction(
        lambda: [
            fake.sentence(nb_words=random.randint(6, 14)).rstrip(".")
            for _ in range(random.randint(2, 5))
        ]
    )
    evidence = factory.LazyFunction(
        lambda: [
            EvidenceItemFactory()
            for _ in range(random.randint(0, 3))
        ]
    )
    visual = factory.SubFactory(VisualFactory)
    takeaway = factory.LazyFunction(
        lambda: fake.sentence(nb_words=random.randint(8, 16)).rstrip(".") + "."
    )
    speaker_notes = factory.LazyFunction(
        lambda: fake.paragraph(nb_sentences=random.randint(1, 3))
    )
    assets_needed = factory.LazyFunction(
        lambda: [
            random.choice([
                "icon set", "bar chart", "architecture diagram",
                "timeline graphic", "logo", "photography",
            ])
            for _ in range(random.randint(0, 3))
        ]
    )


# ─────────────────────────────────────────────────────────────────────────────
# AppendixFactory
# ─────────────────────────────────────────────────────────────────────────────


class AppendixFactory(PydanticFactory):
    """Generates an Appendix with 0–3 appendix slides."""

    class Meta:
        model = Appendix

    @classmethod
    def _create(cls, model_class: type, *args: Any, **kwargs: Any) -> Appendix:
        if "slides" not in kwargs:
            count = random.randint(0, 3)
            kwargs["slides"] = [
                SlideFactory(slide_id=f"A{i+1:02d}", section="Appendix")
                for i in range(count)
            ]
        return model_class(**kwargs)

    @classmethod
    def _build(cls, model_class: type, *args: Any, **kwargs: Any) -> Appendix:
        return cls._create(model_class, *args, **kwargs)

    slides = factory.LazyFunction(list)  # default; overridden in _create


# ─────────────────────────────────────────────────────────────────────────────
# DeckFactory
# ─────────────────────────────────────────────────────────────────────────────


class DeckFactory(PydanticFactory):
    """Generates a valid Deck with 1–11 main slides and a populated appendix."""

    class Meta:
        model = Deck

    title = factory.LazyFunction(
        lambda: fake.catch_phrase() + " — Executive Strategy Deck"
    )
    type = factory.LazyFunction(lambda: random.choice(list(DeckType)).value)
    audience = factory.LazyFunction(
        lambda: random.choice([
            "C-suite executives",
            "Engineering leadership",
            "Board of Directors",
            "Product and Design teams",
            "External investors",
        ])
    )
    tone = factory.LazyFunction(
        lambda: random.choice([
            "Authoritative and data-driven",
            "Confident but approachable",
            "Urgent and direct",
            "Strategic and forward-looking",
        ])
    )
    decision_inform_ask = factory.LazyFunction(
        lambda: random.choice(list(DecisionInformAsk)).value
    )
    context = factory.LazyFunction(
        lambda: fake.paragraph(nb_sentences=3)
    )
    source_material_provided = factory.LazyFunction(lambda: random.choice([True, False]))
    total_slides = factory.LazyFunction(lambda: random.randint(3, 11))

    @classmethod
    def _create(cls, model_class: type, *args: Any, **kwargs: Any) -> Deck:
        if "slides" not in kwargs:
            count = kwargs.get("total_slides", random.randint(3, 11))
            kwargs["slides"] = [
                SlideFactory(slide_id=f"{i+1:02d}")
                for i in range(count)
            ]
        if "appendix" not in kwargs:
            kwargs["appendix"] = AppendixFactory()
        return model_class(**kwargs)

    @classmethod
    def _build(cls, model_class: type, *args: Any, **kwargs: Any) -> Deck:
        return cls._create(model_class, *args, **kwargs)

    slides = factory.LazyFunction(list)      # default; overridden in _create
    appendix = factory.LazyFunction(Appendix)  # default; overridden in _create


# ─────────────────────────────────────────────────────────────────────────────
# DeckEnvelopeFactory
# ─────────────────────────────────────────────────────────────────────────────


class DeckEnvelopeFactory(PydanticFactory):
    """Generates a DeckEnvelope. Defaults to COMPLETE status with a full Deck."""

    class Meta:
        model = DeckEnvelope

    session_id = factory.LazyFunction(
        lambda: "sess-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    )
    status = PipelineStatus.COMPLETE
    deck = factory.SubFactory(DeckFactory)
    error = None
    created_at = factory.LazyFunction(_utcnow_iso)
    completed_at = factory.LazyFunction(_utcnow_iso)

    @classmethod
    def pending(cls, **kwargs: Any) -> DeckEnvelope:
        """Convenience constructor for an in-progress envelope."""
        return cls(
            status=PipelineStatus.GENERATING_SLIDES,
            deck=None,
            completed_at=None,
            **kwargs,
        )

    @classmethod
    def failed(cls, error: str = "LLM timeout after 120s", **kwargs: Any) -> DeckEnvelope:
        """Convenience constructor for a failed envelope."""
        return cls(
            status=PipelineStatus.FAILED,
            deck=None,
            error=error,
            completed_at=None,
            **kwargs,
        )


# ─────────────────────────────────────────────────────────────────────────────
# DeckRequestFactory
# ─────────────────────────────────────────────────────────────────────────────


class DeckRequestFactory(PydanticFactory):
    """
    Generates a valid DeckRequest.
    By default sets ``context`` only (no source_material) to keep things minimal.
    Override ``source_material`` when tests need both inputs.
    """

    class Meta:
        model = DeckRequest

    context = factory.LazyFunction(
        lambda: fake.paragraph(nb_sentences=random.randint(2, 5))
    )
    number_of_slides = factory.LazyFunction(lambda: random.randint(5, 11))
    audience = factory.LazyFunction(
        lambda: random.choice([
            "C-suite executives",
            "Engineering VPs",
            "Board of Directors",
            "Product managers and designers",
            "External investors",
        ])
    )
    deck_type = factory.LazyFunction(lambda: random.choice(list(DeckType)))
    decision_inform_ask = factory.LazyFunction(
        lambda: random.choice(list(DecisionInformAsk))
    )
    tone = factory.LazyFunction(
        lambda: random.choice([
            "Authoritative and data-driven",
            "Confident but approachable",
            "Urgent and direct",
        ])
    )
    source_material = None
    must_include_sections = None
    brand_style_guide = None
    top_messages = None
    known_metrics = None
