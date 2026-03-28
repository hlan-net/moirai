"""Tests for Phase 1: Step-level tracing infrastructure.

Covers SessionLogger step methods, TracingMCPClient step recording and retry,
and LLM call tracing integration.
"""

import json
import os
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_PASSWORD", "test-password")

import pytest

from tasks.session_logger import SessionLogger, SESSION_TTL_SECONDS
from tasks.tracing_mcp_client import TracingMCPClient, DESTRUCTIVE_TOOLS, _truncate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    r = MagicMock()
    r.pipeline.return_value = r
    r.execute.return_value = []
    return r


@pytest.fixture
def session_logger(mock_redis):
    return SessionLogger(mock_redis)


@pytest.fixture
def mock_inner_client():
    """A mock MCP client with a call_tool method."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_session_logger():
    """A mock session logger for TracingMCPClient tests."""
    return MagicMock(spec=SessionLogger)


@pytest.fixture
def tracing_client(mock_inner_client, mock_session_logger):
    return TracingMCPClient(
        mcp_client=mock_inner_client,
        session_logger=mock_session_logger,
        session_id="test-session-123",
        max_retries=3,
    )


# ===========================================================================
# SessionLogger step methods
# ===========================================================================


class TestSessionLoggerSteps:
    def test_add_step_persists_to_redis(self, session_logger, mock_redis):
        step = {"step_id": "s1", "step_type": "tool_call", "tool_name": "read_feed"}
        session_logger.add_step("sess-1", step)

        mock_redis.rpush.assert_called_once_with(
            "session:steps:sess-1", json.dumps(step)
        )
        mock_redis.expire.assert_called_once_with(
            "session:steps:sess-1", SESSION_TTL_SECONDS
        )

    def test_add_step_noop_without_redis(self):
        sl = SessionLogger(None)
        sl.add_step("sess-1", {"x": 1})  # should not raise

    def test_add_step_noop_without_session_id(self, session_logger):
        session_logger.add_step("", {"x": 1})  # should not raise

    def test_get_steps_returns_parsed_dicts(self, session_logger, mock_redis):
        steps = [
            {"step_id": "s1", "tool_name": "read_feed"},
            {"step_id": "s2", "tool_name": "search_issues"},
        ]
        mock_redis.lrange.return_value = [json.dumps(s) for s in steps]

        result = session_logger.get_steps("sess-1")

        assert result == steps
        mock_redis.lrange.assert_called_once_with("session:steps:sess-1", 0, -1)

    def test_get_steps_empty_when_no_steps(self, session_logger, mock_redis):
        mock_redis.lrange.return_value = []
        assert session_logger.get_steps("sess-1") == []

    def test_get_steps_empty_without_redis(self):
        sl = SessionLogger(None)
        assert sl.get_steps("sess-1") == []

    def test_get_steps_handles_exception(self, session_logger, mock_redis):
        mock_redis.lrange.side_effect = Exception("Redis down")
        assert session_logger.get_steps("sess-1") == []


# ===========================================================================
# TracingMCPClient
# ===========================================================================


class TestTracingMCPClient:
    def test_successful_tool_call_records_step(self, tracing_client, mock_inner_client, mock_session_logger):
        mock_inner_client.call_tool.return_value = {
            "status": "success",
            "data": {"feed_id": "f1"},
            "correlation_id": "corr-1",
        }

        result = tracing_client.call_tool("read_feed", userspace="ws-1")

        assert result["status"] == "success"
        # Verify step was recorded
        mock_session_logger.add_step.assert_called_once()
        step = mock_session_logger.add_step.call_args[0][1]
        assert step["step_type"] == "tool_call"
        assert step["tool_name"] == "read_feed"
        assert step["status"] == "success"
        assert step["risk_level"] == "normal"
        assert step["attempt"] == 1
        assert step["correlation_id"] == "corr-1"
        assert "latency_ms" in step

    def test_error_tool_call_records_error_step(self, tracing_client, mock_inner_client, mock_session_logger):
        mock_inner_client.call_tool.return_value = {
            "status": "error",
            "error_code": "RESOURCE_NOT_FOUND",
            "message": "Feed not found",
            "retryable": False,
        }

        result = tracing_client.call_tool("read_feed", userspace="ws-1")

        assert result["status"] == "error"
        step = mock_session_logger.add_step.call_args[0][1]
        assert step["status"] == "error"
        assert step["error_code"] == "RESOURCE_NOT_FOUND"
        assert step["error_message"] == "Feed not found"

    def test_destructive_tool_flagged(self, tracing_client, mock_inner_client, mock_session_logger):
        mock_inner_client.call_tool.return_value = {"status": "success", "data": {}}

        tracing_client.call_tool("delete_feed", userspace="ws-1")

        step = mock_session_logger.add_step.call_args[0][1]
        assert step["risk_level"] == "destructive"

    def test_non_dict_result_recorded(self, tracing_client, mock_inner_client, mock_session_logger):
        mock_inner_client.call_tool.return_value = "legacy string result"

        result = tracing_client.call_tool("some_tool", userspace="ws-1")

        assert result == "legacy string result"
        step = mock_session_logger.add_step.call_args[0][1]
        assert step["status"] == "success"
        assert "legacy string result" in step["output_summary"]

    def test_exception_records_error_step_and_reraises(
        self, tracing_client, mock_inner_client, mock_session_logger
    ):
        mock_inner_client.call_tool.side_effect = ConnectionError("timeout")

        with pytest.raises(ConnectionError, match="timeout"):
            tracing_client.call_tool("read_feed", userspace="ws-1")

        step = mock_session_logger.add_step.call_args[0][1]
        assert step["status"] == "error"
        assert "timeout" in step["error_message"]

    def test_retries_on_transient_error(self, tracing_client, mock_inner_client, mock_session_logger):
        # First call: retryable error. Second call: success.
        mock_inner_client.call_tool.side_effect = [
            {
                "status": "error",
                "error_code": "TRANSIENT_NETWORK",
                "message": "timeout",
                "retryable": True,
                "retry_after_ms": 10,  # short for testing
            },
            {"status": "success", "data": {"ok": True}},
        ]

        result = tracing_client.call_tool("read_feed", userspace="ws-1")

        assert result["status"] == "success"
        assert mock_inner_client.call_tool.call_count == 2
        # Two steps recorded: one "retried", one "success"
        assert mock_session_logger.add_step.call_count == 2
        first_step = mock_session_logger.add_step.call_args_list[0][0][1]
        second_step = mock_session_logger.add_step.call_args_list[1][0][1]
        assert first_step["status"] == "retried"
        assert first_step["attempt"] == 1
        assert second_step["status"] == "success"
        assert second_step["attempt"] == 2

    def test_retries_exhausted_returns_last_error(self, mock_inner_client, mock_session_logger):
        client = TracingMCPClient(
            mcp_client=mock_inner_client,
            session_logger=mock_session_logger,
            session_id="sess-1",
            max_retries=2,
        )
        error_response = {
            "status": "error",
            "error_code": "DATABASE_UNAVAILABLE",
            "message": "db down",
            "retryable": True,
            "retry_after_ms": 10,
        }
        mock_inner_client.call_tool.return_value = error_response

        result = client.call_tool("read_feed", userspace="ws-1")

        # Last attempt is NOT retried (attempt == max_retries), recorded as error
        assert result["status"] == "error"
        assert mock_inner_client.call_tool.call_count == 2
        last_step = mock_session_logger.add_step.call_args_list[-1][0][1]
        assert last_step["status"] == "error"

    def test_no_retries_when_max_zero(self, mock_inner_client, mock_session_logger):
        client = TracingMCPClient(
            mcp_client=mock_inner_client,
            session_logger=mock_session_logger,
            session_id="sess-1",
            max_retries=1,  # single attempt, no retries
        )
        mock_inner_client.call_tool.return_value = {
            "status": "error",
            "retryable": True,
            "retry_after_ms": 10,
        }

        result = client.call_tool("read_feed")

        assert mock_inner_client.call_tool.call_count == 1

    def test_proxy_passthrough(self, tracing_client, mock_inner_client):
        """Non-call_tool attributes are proxied to the inner client."""
        mock_inner_client.some_attr = "hello"
        assert tracing_client.some_attr == "hello"

    def test_session_logger_and_session_id_exposed(self, tracing_client, mock_session_logger):
        assert tracing_client.session_logger is mock_session_logger
        assert tracing_client.session_id == "test-session-123"


# ===========================================================================
# DESTRUCTIVE_TOOLS set
# ===========================================================================


class TestDestructiveTools:
    @pytest.mark.parametrize(
        "tool_name",
        ["delete_issue", "delete_event", "delete_trend", "delete_feed",
         "delete_stale_entities", "publish_to_bluesky", "delete_user"],
    )
    def test_destructive_tools_in_set(self, tool_name):
        assert tool_name in DESTRUCTIVE_TOOLS

    @pytest.mark.parametrize(
        "tool_name",
        ["read_feed", "search_issues", "add_event", "list_users"],
    )
    def test_safe_tools_not_in_set(self, tool_name):
        assert tool_name not in DESTRUCTIVE_TOOLS


# ===========================================================================
# _truncate helper
# ===========================================================================


class TestTruncate:
    def test_short_string_unchanged(self):
        assert _truncate("hello") == "hello"

    def test_long_string_truncated(self):
        result = _truncate("a" * 600, 100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_exact_length_unchanged(self):
        s = "x" * 500
        assert _truncate(s) == s
