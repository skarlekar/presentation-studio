"""
Unit tests for SessionService — in-memory session store with HITL checkpoints.
"""
import asyncio
import pytest

from services.session_service import SessionService
from schemas.output import PipelineStatus, CheckpointStatus


@pytest.fixture
def svc():
    return SessionService()


@pytest.fixture
def request_data():
    return {
        "context": "Test deck context",
        "number_of_slides": 11,
        "audience": "C-suite",
        "deck_type": "Decision Deck",
        "decision_inform_ask": "Decision",
        "tone": "Authoritative",
    }


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_creates_session_with_uuid(self, svc, request_data):
        session = await svc.create_session(request_data)
        assert session.session_id
        assert len(session.session_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_initial_status_is_pending(self, svc, request_data):
        session = await svc.create_session(request_data)
        assert session.status == PipelineStatus.PENDING

    @pytest.mark.asyncio
    async def test_stores_request_data(self, svc, request_data):
        session = await svc.create_session(request_data)
        assert session.request_data == request_data


class TestGetSession:
    @pytest.mark.asyncio
    async def test_returns_created_session(self, svc, request_data):
        created = await svc.create_session(request_data)
        retrieved = await svc.get_session(created.session_id)
        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_id(self, svc):
        result = await svc.get_session("nonexistent-id")
        assert result is None


class TestUpdateStatus:
    @pytest.mark.asyncio
    async def test_updates_pipeline_status(self, svc, request_data):
        session = await svc.create_session(request_data)
        await svc.update_status(session.session_id, PipelineStatus.RUNNING)
        updated = await svc.get_session(session.session_id)
        assert updated.status == PipelineStatus.RUNNING

    @pytest.mark.asyncio
    async def test_updates_current_stage(self, svc, request_data):
        session = await svc.create_session(request_data)
        await svc.update_status(session.session_id, PipelineStatus.RUNNING, current_stage="insight_extractor")
        updated = await svc.get_session(session.session_id)
        assert updated.current_stage == "insight_extractor"

    @pytest.mark.asyncio
    async def test_updates_error(self, svc, request_data):
        session = await svc.create_session(request_data)
        await svc.update_status(session.session_id, PipelineStatus.FAILED, error="Timeout")
        updated = await svc.get_session(session.session_id)
        assert updated.error == "Timeout"

    @pytest.mark.asyncio
    async def test_no_op_for_unknown_session(self, svc):
        # Should not raise
        await svc.update_status("nonexistent", PipelineStatus.RUNNING)


class TestAddCheckpoint:
    @pytest.mark.asyncio
    async def test_adds_checkpoint(self, svc, request_data):
        session = await svc.create_session(request_data)
        cp = await svc.add_checkpoint(
            session.session_id,
            "insight_extractor",
            {"core_problem": "TCO is too high"},
        )
        assert cp.checkpoint_id
        assert cp.stage == "insight_extractor"
        assert cp.status == CheckpointStatus.PENDING

    @pytest.mark.asyncio
    async def test_sets_session_to_awaiting_approval(self, svc, request_data):
        session = await svc.create_session(request_data)
        await svc.add_checkpoint(session.session_id, "deck_architect", {})
        updated = await svc.get_session(session.session_id)
        assert updated.status == PipelineStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_raises_for_unknown_session(self, svc):
        with pytest.raises(ValueError, match="not found"):
            await svc.add_checkpoint("nonexistent", "stage", {})

    @pytest.mark.asyncio
    async def test_stage_index_set_correctly(self, svc, request_data):
        session = await svc.create_session(request_data)
        cp = await svc.add_checkpoint(session.session_id, "slide_generator", {})
        assert cp.stage_index == 3  # slide_generator is stage 3


class TestResolveCheckpoint:
    @pytest.mark.asyncio
    async def test_approve_checkpoint(self, svc, request_data):
        session = await svc.create_session(request_data)
        cp = await svc.add_checkpoint(session.session_id, "insight_extractor", {})
        resolved = await svc.resolve_checkpoint(session.session_id, cp.checkpoint_id, "approved")
        assert resolved.status == CheckpointStatus.APPROVED

    @pytest.mark.asyncio
    async def test_reject_checkpoint(self, svc, request_data):
        session = await svc.create_session(request_data)
        cp = await svc.add_checkpoint(session.session_id, "insight_extractor", {})
        resolved = await svc.resolve_checkpoint(session.session_id, cp.checkpoint_id, "rejected")
        assert resolved.status == CheckpointStatus.REJECTED

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_checkpoint(self, svc, request_data):
        session = await svc.create_session(request_data)
        result = await svc.resolve_checkpoint(session.session_id, "nonexistent-cp", "approved")
        assert result is None


class TestProgressPct:
    @pytest.mark.asyncio
    async def test_returns_0_when_pending(self, svc, request_data):
        session = await svc.create_session(request_data)
        assert session.progress_pct() == 0 or session.progress_pct() == 5

    @pytest.mark.asyncio
    async def test_returns_100_when_completed(self, svc, request_data):
        session = await svc.create_session(request_data)
        await svc.update_status(session.session_id, PipelineStatus.COMPLETED)
        updated = await svc.get_session(session.session_id)
        assert updated.progress_pct() == 100


class TestCleanupExpired:
    @pytest.mark.asyncio
    async def test_removes_old_sessions(self, svc, request_data):
        session = await svc.create_session(request_data)
        # Manually backdate the session
        from datetime import datetime, timedelta
        svc._sessions[session.session_id].created_at = datetime.utcnow() - timedelta(days=2)
        removed = await svc.cleanup_expired()
        assert removed == 1
        assert await svc.get_session(session.session_id) is None

    @pytest.mark.asyncio
    async def test_keeps_recent_sessions(self, svc, request_data):
        session = await svc.create_session(request_data)
        removed = await svc.cleanup_expired()
        assert removed == 0
        assert await svc.get_session(session.session_id) is not None
