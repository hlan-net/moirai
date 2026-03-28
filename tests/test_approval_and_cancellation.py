"""Tests for Phase 2+3: Retry config, approval gate, cancellation, and API routes."""

import json
import os
from unittest.mock import MagicMock

os.environ.setdefault("ADMIN_PASSWORD", "test-password")

import pytest

from tasks.session_logger import (
    SessionLogger,
    STATUS_CANCELLED,
    STATUS_ERROR,
)
from tasks.tracing_mcp_client import (
    AgentCancelledException,
    TracingMCPClient,
    _APPROVAL_QUEUE_PREFIX,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    r = MagicMock()
    return r


@pytest.fixture
def mock_session_logger():
    return MagicMock(spec=SessionLogger)


@pytest.fixture
def mock_inner_client():
    return MagicMock()


def _make_tracing_client(
    inner, sl, redis=None, require_approval=False, approval_timeout=2, max_retries=1
):
    return TracingMCPClient(
        mcp_client=inner,
        session_logger=sl,
        session_id="sess-1",
        redis_client=redis,
        max_retries=max_retries,
        require_approval=require_approval,
        approval_timeout=approval_timeout,
        userspace="ws-1",
        agent_name="test-agent",
    )


# ===========================================================================
# Cancellation
# ===========================================================================


class TestCancellation:
    def test_cancelled_before_tool_call(
        self, mock_inner_client, mock_session_logger, mock_redis
    ):
        mock_redis.get.return_value = b"1"  # cancel flag set
        client = _make_tracing_client(
            mock_inner_client, mock_session_logger, redis=mock_redis
        )

        with pytest.raises(AgentCancelledException):
            client.call_tool("read_feed", userspace="ws-1")

        # Tool should NOT have been called
        mock_inner_client.call_tool.assert_not_called()

    def test_not_cancelled_when_flag_absent(
        self, mock_inner_client, mock_session_logger, mock_redis
    ):
        mock_redis.get.return_value = None
        mock_inner_client.call_tool.return_value = {"status": "success", "data": {}}
        client = _make_tracing_client(
            mock_inner_client, mock_session_logger, redis=mock_redis
        )

        result = client.call_tool("read_feed", userspace="ws-1")
        assert result["status"] == "success"

    def test_cancellation_check_tolerates_redis_error(
        self, mock_inner_client, mock_session_logger, mock_redis
    ):
        mock_redis.get.side_effect = ConnectionError("Redis down")
        mock_inner_client.call_tool.return_value = {"status": "success", "data": {}}
        client = _make_tracing_client(
            mock_inner_client, mock_session_logger, redis=mock_redis
        )

        # Should NOT raise — Redis errors are swallowed
        result = client.call_tool("read_feed", userspace="ws-1")
        assert result["status"] == "success"

    def test_no_cancellation_check_without_redis(
        self, mock_inner_client, mock_session_logger
    ):
        mock_inner_client.call_tool.return_value = {"status": "success", "data": {}}
        client = _make_tracing_client(mock_inner_client, mock_session_logger)

        result = client.call_tool("read_feed", userspace="ws-1")
        assert result["status"] == "success"


# ===========================================================================
# Approval gate
# ===========================================================================


class TestApprovalGate:
    def test_approval_skipped_for_safe_tools(
        self, mock_inner_client, mock_session_logger, mock_redis
    ):
        """Non-destructive tools bypass approval even when require_approval=True."""
        mock_redis.get.return_value = None  # no cancel flag
        mock_inner_client.call_tool.return_value = {"status": "success", "data": {}}
        client = _make_tracing_client(
            mock_inner_client,
            mock_session_logger,
            redis=mock_redis,
            require_approval=True,
        )

        result = client.call_tool("read_feed", userspace="ws-1")
        assert result["status"] == "success"
        # No approval request written
        mock_redis.hset.assert_not_called()

    def test_approval_skipped_when_not_required(
        self, mock_inner_client, mock_session_logger, mock_redis
    ):
        """Destructive tools execute without approval when require_approval=False."""
        mock_redis.get.return_value = None
        mock_inner_client.call_tool.return_value = {"status": "success", "data": {}}
        client = _make_tracing_client(
            mock_inner_client,
            mock_session_logger,
            redis=mock_redis,
            require_approval=False,
        )

        result = client.call_tool("delete_feed", userspace="ws-1")
        assert result["status"] == "success"
        mock_redis.hset.assert_not_called()

    def test_approved_action_executes(
        self, mock_inner_client, mock_session_logger, mock_redis
    ):
        """When approved, the destructive tool call proceeds."""
        # get() calls: 1st for cancel check, then approval polling returns "approved"
        mock_redis.get.side_effect = [None, b"approved"]
        mock_inner_client.call_tool.return_value = {"status": "success", "data": {}}
        client = _make_tracing_client(
            mock_inner_client,
            mock_session_logger,
            redis=mock_redis,
            require_approval=True,
            approval_timeout=5,
        )

        result = client.call_tool("delete_feed", userspace="ws-1")

        assert result["status"] == "success"
        mock_inner_client.call_tool.assert_called_once()
        # Approval request was written
        mock_redis.hset.assert_called_once()

    def test_denied_action_returns_error(
        self, mock_inner_client, mock_session_logger, mock_redis
    ):
        """When denied, the tool call is NOT executed."""
        mock_redis.get.side_effect = [None, b"denied"]
        client = _make_tracing_client(
            mock_inner_client,
            mock_session_logger,
            redis=mock_redis,
            require_approval=True,
            approval_timeout=5,
        )

        result = client.call_tool("delete_feed", userspace="ws-1")

        assert result["status"] == "error"
        assert result["error_code"] == "APPROVAL_DENIED"
        mock_inner_client.call_tool.assert_not_called()
        # Denied step recorded
        steps = [
            c[0][1]
            for c in mock_session_logger.add_step.call_args_list
            if c[0][1].get("status") == "denied"
        ]
        assert len(steps) >= 1

    def test_timeout_returns_error(
        self, mock_inner_client, mock_session_logger, mock_redis
    ):
        """When no decision arrives within timeout, returns error."""
        mock_redis.get.return_value = None  # never a decision
        client = _make_tracing_client(
            mock_inner_client,
            mock_session_logger,
            redis=mock_redis,
            require_approval=True,
            approval_timeout=1,  # 1 second timeout for fast test
        )

        result = client.call_tool("delete_feed", userspace="ws-1")

        assert result["status"] == "error"
        assert result["error_code"] == "APPROVAL_TIMEOUT"
        mock_inner_client.call_tool.assert_not_called()

    def test_approval_writes_to_redis_queue(
        self, mock_inner_client, mock_session_logger, mock_redis
    ):
        """Approval request is written to Redis hash + queue."""
        mock_redis.get.side_effect = [None, b"approved"]
        mock_inner_client.call_tool.return_value = {"status": "success", "data": {}}
        client = _make_tracing_client(
            mock_inner_client,
            mock_session_logger,
            redis=mock_redis,
            require_approval=True,
            approval_timeout=5,
        )

        client.call_tool("delete_feed", userspace="ws-1")

        # Verify hset was called with approval pending data
        hset_call = mock_redis.hset.call_args
        assert hset_call is not None
        mapping = hset_call[1]["mapping"]
        assert mapping["tool_name"] == "delete_feed"
        assert mapping["userspace"] == "ws-1"
        assert mapping["agent_name"] == "test-agent"

        # Verify lpush to queue
        mock_redis.lpush.assert_called_once()
        queue_key = mock_redis.lpush.call_args[0][0]
        assert queue_key == f"{_APPROVAL_QUEUE_PREFIX}ws-1"


# ===========================================================================
# Session context manager — cancellation status
# ===========================================================================


class TestSessionContextCancellation:
    def _setup_redis_for_session(self):
        """Create a mock Redis that stores session docs written via pipeline."""
        mock_redis = MagicMock()
        mock_redis.llen.return_value = 0
        pipe = mock_redis.pipeline.return_value
        pipe.execute.return_value = []

        # Capture what pipeline.set() writes so finish_session can read it back
        stored = {}

        def fake_pipe_set(key, value, ex=None):
            stored[key] = value

        pipe.set.side_effect = fake_pipe_set

        def fake_get(key):
            return stored.get(key)

        mock_redis.get.side_effect = fake_get

        return mock_redis, pipe, stored

    def test_cancelled_exception_sets_cancelled_status(self):
        mock_redis, pipe, stored = self._setup_redis_for_session()
        sl = SessionLogger(mock_redis)

        with pytest.raises(AgentCancelledException):
            with sl.session(
                session_type="scheduled_agent",
                userspace="ws-1",
            ):
                raise AgentCancelledException("cancelled by operator")

        # Find the final persisted doc (last pipeline set call)
        set_calls = [c for c in pipe.method_calls if c[0] == "set"]
        assert len(set_calls) >= 2  # start + finish
        last_doc = json.loads(set_calls[-1][1][1])
        assert last_doc["status"] == STATUS_CANCELLED

    def test_regular_exception_sets_error_status(self):
        mock_redis, pipe, stored = self._setup_redis_for_session()
        sl = SessionLogger(mock_redis)

        with pytest.raises(ValueError):
            with sl.session(
                session_type="scheduled_agent",
                userspace="ws-1",
            ):
                raise ValueError("something broke")

        set_calls = [c for c in pipe.method_calls if c[0] == "set"]
        assert len(set_calls) >= 2
        last_doc = json.loads(set_calls[-1][1][1])
        assert last_doc["status"] == STATUS_ERROR


# ===========================================================================
# Agent config schema fields
# ===========================================================================


class TestAgentConfigSchemaFields:
    def test_default_values(self):
        from api.validation import AgentConfigBase

        config = AgentConfigBase(
            name="test",
            trigger_type="scheduled",
            target_db="issues",
            logic_module="tasks.agent_logic.create_event_from_articles",
            schedule_interval="1h",
        )
        assert config.max_retries == 3
        assert config.require_approval is False
        assert config.approval_timeout_seconds == 300

    def test_custom_values(self):
        from api.validation import AgentConfigBase

        config = AgentConfigBase(
            name="test",
            trigger_type="scheduled",
            target_db="issues",
            logic_module="tasks.agent_logic.create_event_from_articles",
            schedule_interval="1h",
            max_retries=5,
            require_approval=True,
            approval_timeout_seconds=600,
        )
        assert config.max_retries == 5
        assert config.require_approval is True
        assert config.approval_timeout_seconds == 600

    def test_max_retries_bounds(self):
        from pydantic import ValidationError
        from api.validation import AgentConfigBase

        with pytest.raises(ValidationError):
            AgentConfigBase(
                name="test",
                trigger_type="scheduled",
                target_db="issues",
                logic_module="tasks.agent_logic.create_event_from_articles",
                schedule_interval="1h",
                max_retries=11,  # > 10
            )

    def test_approval_timeout_bounds(self):
        from pydantic import ValidationError
        from api.validation import AgentConfigBase

        with pytest.raises(ValidationError):
            AgentConfigBase(
                name="test",
                trigger_type="scheduled",
                target_db="issues",
                logic_module="tasks.agent_logic.create_event_from_articles",
                schedule_interval="1h",
                approval_timeout_seconds=10,  # < 30
            )


# ===========================================================================
# STATUS_CANCELLED constant
# ===========================================================================


class TestStatusConstants:
    def test_status_cancelled_exists(self):
        assert STATUS_CANCELLED == "cancelled"
