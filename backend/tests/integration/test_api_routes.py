"""
Integration tests for FastAPI routes — uses HTTPX TestClient.
Tests all /api/deck/* endpoints with the session service in memory.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from backend.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Health route ──────────────────────────────────────────────────────────────

class TestHealthRoute:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_has_timestamp(self, client):
        resp = client.get("/api/health")
        assert "timestamp" in resp.json()


# ── Generate endpoint ─────────────────────────────────────────────────────────

class TestGenerateEndpoint:
    def valid_payload(self):
        return {
            "context": "We need to build a business case for cloud migration.",
            "number_of_slides": 11,
            "audience": "C-suite executives",
            "deck_type": "Decision Deck",
            "decision_inform_ask": "Decision",
            "tone": "Authoritative and data-driven",
        }

    def test_generate_returns_202(self, client):
        resp = client.post("/api/deck/generate", json=self.valid_payload())
        assert resp.status_code == 202

    def test_generate_returns_session_id(self, client):
        resp = client.post("/api/deck/generate", json=self.valid_payload())
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) == 36

    def test_generate_missing_required_fields_returns_422(self, client):
        resp = client.post("/api/deck/generate", json={"context": "test"})
        assert resp.status_code == 422

    def test_generate_missing_context_and_source_material_returns_422(self, client):
        payload = self.valid_payload()
        payload["context"] = None
        resp = client.post("/api/deck/generate", json=payload)
        assert resp.status_code == 422

    def test_generate_slide_count_below_3_returns_422(self, client):
        payload = self.valid_payload()
        payload["number_of_slides"] = 2
        resp = client.post("/api/deck/generate", json=payload)
        assert resp.status_code == 422

    def test_generate_slide_count_above_60_returns_422(self, client):
        payload = self.valid_payload()
        payload["number_of_slides"] = 61
        resp = client.post("/api/deck/generate", json=payload)
        assert resp.status_code == 422


# ── Status endpoint ───────────────────────────────────────────────────────────

class TestStatusEndpoint:
    def test_status_404_for_unknown_session(self, client):
        resp = client.get("/api/deck/nonexistent-session/status")
        assert resp.status_code == 404

    def test_status_returns_session_info(self, client):
        # Create a session first
        create_resp = client.post("/api/deck/generate", json={
            "context": "Test context",
            "number_of_slides": 5,
            "audience": "Test audience",
            "deck_type": "Strategy Deck",
            "decision_inform_ask": "Inform",
            "tone": "Formal",
        })
        assert create_resp.status_code == 202
        session_id = create_resp.json()["session_id"]

        status_resp = client.get(f"/api/deck/{session_id}/status")
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["session_id"] == session_id
        assert "status" in data


# ── Deck retrieval ────────────────────────────────────────────────────────────

class TestDeckEndpoint:
    def test_deck_returns_202_while_running(self, client):
        create_resp = client.post("/api/deck/generate", json={
            "context": "Test",
            "number_of_slides": 5,
            "audience": "Execs",
            "deck_type": "Pitch Deck",
            "decision_inform_ask": "Ask",
            "tone": "Energetic",
        })
        session_id = create_resp.json()["session_id"]
        resp = client.get(f"/api/deck/{session_id}")
        # Should be 202 (still pending/running) or 200 if completed fast
        assert resp.status_code in (200, 202)

    def test_deck_404_for_unknown_session(self, client):
        resp = client.get("/api/deck/nonexistent-session")
        assert resp.status_code == 404


# ── Checkpoint endpoints ──────────────────────────────────────────────────────

class TestCheckpointEndpoints:
    def test_approve_404_for_unknown_session(self, client):
        resp = client.post(
            "/api/deck/nonexistent/checkpoint/cp-001/approve",
            json={"comment": "OK"},
        )
        assert resp.status_code == 404

    def test_reject_404_for_unknown_session(self, client):
        resp = client.post(
            "/api/deck/nonexistent/checkpoint/cp-001/reject",
            json={"feedback": "Titles are not conclusion statements — fix them all."},
        )
        assert resp.status_code == 404


# ── Export endpoint ───────────────────────────────────────────────────────────

class TestExportEndpoint:
    def test_export_404_for_unknown_session(self, client):
        resp = client.post("/api/deck/nonexistent/export")
        assert resp.status_code == 404

    def test_history_404_for_unknown_session(self, client):
        resp = client.get("/api/deck/nonexistent/history")
        assert resp.status_code == 404

    def test_approve_deck_404_for_unknown_session(self, client):
        resp = client.post("/api/deck/nonexistent/approve")
        assert resp.status_code == 404
