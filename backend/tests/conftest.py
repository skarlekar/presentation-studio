"""
DeckStudio test configuration and shared fixtures.

Fixture inventory:
  mock_llm              — MagicMock replacing the LangChain LLM client
  sample_deck_request   — Full DeckRequest with all optional fields populated
  minimal_deck_request  — DeckRequest with only required fields
  sample_slide          — Valid Slide instance for unit tests
  sample_deck_envelope  — Complete DeckEnvelope with status=COMPLETE
  async_client          — AsyncClient for integration tests (requires FastAPI app)

All fixtures are session-scoped or function-scoped as appropriate.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from schemas.input import DeckRequest, DeckType, DecisionInformAsk
from schemas.output import (
    Appendix,
    Checkpoint,
    CheckpointStatus,
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


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# mock_llm
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm() -> Generator[MagicMock, None, None]:
    """
    A MagicMock that replaces the LangChain LLM client.

    The mock's ``.ainvoke`` is pre-configured to return a plausible
    AIMessage-like object with ``.content`` containing a minimal valid JSON deck.

    Usage in tests:
        def test_something(mock_llm):
            mock_llm.ainvoke.return_value.content = '{"deck": {...}}'
    """
    mock = MagicMock()
    mock.ainvoke = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"deck": {"title": "Test Deck", "type": "Decision Deck", '
                '"audience": "Executives", "tone": "Direct", '
                '"decision_inform_ask": "Decision", "context": "Test context.", '
                '"source_material_provided": false, "total_slides": 1, '
                '"slides": [], "appendix": {"slides": []}}}'
            )
        )
    )
    mock.invoke = MagicMock(
        return_value=MagicMock(
            content="Test LLM response"
        )
    )

    with patch("config.settings.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test-key",
            anthropic_model="claude-3-5-sonnet-20241022",
            openai_api_key=None,
            openai_model="gpt-4o",
            llm_temperature=0.3,
            llm_max_tokens=8192,
            llm_timeout_seconds=120,
            checkpoint_enabled=True,
            checkpoint_stages=["outline", "review"],
            session_ttl_seconds=3600,
            langsmith_tracing=False,
            is_development=True,
            is_production=False,
        )
        yield mock


# ─────────────────────────────────────────────────────────────────────────────
# DeckRequest fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_deck_request() -> DeckRequest:
    """
    A fully-populated DeckRequest for tests that need realistic input data.
    All optional fields are explicitly set.
    """
    return DeckRequest(
        context=(
            "We need to present the business case for migrating our on-premise "
            "data infrastructure to a cloud-native event-driven architecture. "
            "The current system has 8 disconnected document stores causing "
            "integration overhead of ~40% of engineering capacity."
        ),
        number_of_slides=11,
        audience="C-suite executives (CTO, CFO, CIO) at a Fortune 500 financial services firm",
        deck_type=DeckType.DECISION,
        decision_inform_ask=DecisionInformAsk.DECISION,
        tone="Authoritative, data-driven, executive-grade",
        source_material=(
            "Q3 Engineering Report: Integration costs represent 38% of total "
            "engineering spend. Cloud-native pilot reduced onboarding time from "
            "5 weeks to 3 weeks. Projected ROI: 18-month payback period."
        ),
        must_include_sections=["Executive Summary", "Risk & Mitigations", "Decision / CTA"],
        brand_style_guide="Minimal consulting style: navy blue (#002B5C) and slate grey (#4A5568), flat icons",
        top_messages=[
            "Integration overhead is costing us 38% of engineering capacity",
            "A cloud-native event-driven architecture reduces this by 40%",
            "18-month payback period with measurable ROI",
        ],
        known_metrics=[
            "38% engineering spend on integration",
            "Pilot: 5 weeks → 3 weeks onboarding",
            "18-month ROI payback",
        ],
    )


@pytest.fixture
def minimal_deck_request() -> DeckRequest:
    """
    A minimal DeckRequest with only required fields.
    Source material is omitted; context alone satisfies the at-least-one rule.
    """
    return DeckRequest(
        context="Quarterly strategy update for the engineering leadership team.",
        number_of_slides=5,
        audience="Engineering leadership",
        deck_type=DeckType.UPDATE,
        decision_inform_ask=DecisionInformAsk.INFORM,
        tone="Direct and concise",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Slide fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_slide() -> Slide:
    """
    A valid Slide instance conforming to all schema constraints:
    • metaphor = exactly 1 sentence
    • key_points ≤ 5 items
    • evidence ≤ 3 items
    """
    return Slide(
        slide_id="05",
        section="Insight",
        title="Event-driven ingestion reduces integration time by 40%",
        objective="Convince the audience that the proposed architecture eliminates integration overhead.",
        metaphor=(
            "We're replacing a tangled web of direct phone calls between every team "
            "with a single company bulletin board everyone reads from — "
            "cutting coordination overhead by 40%."
        ),
        key_points=[
            "Standardized ingestion contract eliminates per-source integration",
            "Replay capability improves reliability and auditing",
            "Decoupling producers and consumers accelerates delivery",
            "Pilot validated: 5-week onboarding reduced to 3 weeks",
            "Pattern adopted by all top-10 global banks",
        ],
        evidence=[
            EvidenceItem(
                type=EvidenceType.METRIC,
                detail="Pilot reduced onboarding from 5 weeks to 3 weeks",
                source="Q3 Engineering Report",
            ),
            EvidenceItem(
                type=EvidenceType.REFERENCE,
                detail="Architecture Review AR-17",
            ),
            EvidenceItem(
                type=EvidenceType.BENCHMARK,
                detail="Industry average integration overhead: 35–45% of engineering spend",
                source="Gartner 2024 Data Integration Report",
            ),
        ],
        visual=Visual(
            layout=LayoutType.TWO_COLUMN,
            illustration_prompt=IllustrationPrompt(
                type=VisualType.ARCHITECTURE_DIAGRAM,
                description=(
                    "Architecture showing event-driven ingestion pipeline with "
                    "producers on the left, event bus in the centre, and consumers on the right."
                ),
                alt_text="Event-driven ingestion pipeline architecture diagram",
            ),
        ),
        takeaway="With the architecture chosen, the next question becomes execution.",
        speaker_notes=(
            "Explain that the 40% estimate excludes initial platform setup costs. "
            "Reference AR-17 if the CTO asks for technical detail."
        ),
        assets_needed=["event bus icon", "architecture icon set", "arrow connectors"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# DeckEnvelope fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_deck_envelope(sample_slide: Slide) -> DeckEnvelope:
    """
    A complete DeckEnvelope in COMPLETE status with a minimal but valid Deck.
    """
    now = _utcnow_iso()

    deck = Deck(
        title="Migrate to Cloud-Native Event-Driven Architecture",
        type=DeckType.DECISION.value,
        audience="C-suite executives at a Fortune 500 financial services firm",
        tone="Authoritative, data-driven, executive-grade",
        decision_inform_ask=DecisionInformAsk.DECISION.value,
        context=(
            "We need to present the business case for migrating our on-premise "
            "data infrastructure to a cloud-native event-driven architecture."
        ),
        source_material_provided=True,
        total_slides=1,
        slides=[sample_slide],
        appendix=Appendix(slides=[]),
    )

    return DeckEnvelope(
        session_id="sess-test-abc123",
        status=PipelineStatus.COMPLETE,
        deck=deck,
        error=None,
        created_at=now,
        completed_at=now,
    )


# ─────────────────────────────────────────────────────────────────────────────
# async_client
# ─────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    HTTPX AsyncClient wired to the FastAPI app via ASGITransport.

    Import is deferred inside the fixture so that tests that do NOT require
    a running app do not trigger application startup side-effects.

    Usage:
        @pytest.mark.integration
        async def test_health(async_client):
            resp = await async_client.get("/health")
            assert resp.status_code == 200
    """
    try:
        from api.app import create_app  # noqa: PLC0415 — intentional lazy import
        app = create_app()
    except ImportError:
        # App not yet implemented — return a stub client that always 404s
        # so integration tests can be written before the app exists.
        from fastapi import FastAPI
        app = FastAPI()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
