"""
Unit tests for file_service.py — versioned JSON export.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.file_service import save_deck, load_deck, list_versions, _slugify


class TestSlugify:
    def test_basic_slug(self):
        assert _slugify("Hello World") == "hello-world"

    def test_strips_special_chars(self):
        assert _slugify("Cloud: Migration! #1") == "cloud-migration-1"

    def test_max_50_chars(self):
        long = "a" * 100
        result = _slugify(long)
        assert len(result) <= 50

    def test_empty_string_returns_deck(self):
        assert _slugify("") == "deck"

    def test_numbers_preserved(self):
        assert "40" in _slugify("40% reduction in TCO")


class TestSaveDeck:
    @pytest.mark.asyncio
    async def test_saves_file_and_returns_metadata(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "backend.services.file_service.get_settings",
            lambda: MagicMock(export_dir=str(tmp_path)),
        )
        # Import here to get patched version
        from backend.services import file_service as fs
        fs.settings = MagicMock(export_dir=str(tmp_path))

        from backend.schemas.output import DeckEnvelope, PipelineStatus, Deck, Appendix
        envelope = DeckEnvelope(
            session_id="sess-001",
            status=PipelineStatus.COMPLETED,
            deck=Deck(
                title="Test Deck",
                type="Decision Deck",
                audience="C-suite",
                tone="Authoritative",
                decision_inform_ask="Decision",
                context="Context",
                source_material_provided=False,
                total_slides=1,
                slides=[],
                appendix=Appendix(slides=[]),
            ),
            created_at="2026-03-10T18:00:00Z",
        )

        result = await save_deck("sess-001", envelope)
        assert result["version"] == 1
        assert result["filename"].endswith("_v1.json")
        assert result["size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_increments_version(self, tmp_path, monkeypatch):
        from backend.services import file_service as fs
        fs.settings = MagicMock(export_dir=str(tmp_path))

        # Create a fake existing file to simulate v1
        (tmp_path / "test-deck_20260310_180000_v1.json").write_text("{}")

        from backend.schemas.output import DeckEnvelope, PipelineStatus, Deck, Appendix
        envelope = DeckEnvelope(
            session_id="s",
            status=PipelineStatus.COMPLETED,
            deck=Deck(
                title="Test Deck",
                type="Strategy Deck",
                audience="Exec",
                tone="Formal",
                decision_inform_ask="Inform",
                context="ctx",
                source_material_provided=False,
                total_slides=1,
                slides=[],
                appendix=Appendix(slides=[]),
            ),
            created_at="2026-03-10T18:00:00Z",
        )

        result = await save_deck("s", envelope)
        assert result["version"] == 2


class TestLoadDeck:
    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_file(self):
        result = await load_deck("/nonexistent/path/deck.json")
        assert result is None


class TestListVersions:
    @pytest.mark.asyncio
    async def test_returns_empty_for_no_files(self, tmp_path, monkeypatch):
        from backend.services import file_service as fs
        fs.settings = MagicMock(export_dir=str(tmp_path))
        result = await list_versions("sess-001")
        assert result == []
