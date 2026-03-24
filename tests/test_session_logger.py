"""Tests for tasks/session_logger.py."""

import json
import pytest
from unittest.mock import MagicMock, call, patch
from tasks.session_logger import (
    SessionLogger,
    SESSION_TTL_SECONDS,
    SESSION_TYPE_SCHEDULED,
    SESSION_TYPE_ON_NEW_ARTICLE,
    SESSION_TYPE_CHAT,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    STATUS_ERROR,
)


@pytest.fixture
def mock_redis():
    client = MagicMock()
    client.pipeline.return_value.__enter__ = MagicMock(return_value=client.pipeline.return_value)
    client.pipeline.return_value.__exit__ = MagicMock(return_value=False)
    return client


@pytest.fixture
def sl(mock_redis):
    return SessionLogger(redis_client=mock_redis)


@pytest.fixture
def sl_no_redis():
    return SessionLogger(redis_client=None)


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------


def test_start_session_returns_uuid(sl):
    sl._redis.pipeline.return_value.execute.return_value = []
    session_id = sl.start_session(
        session_type=SESSION_TYPE_SCHEDULED,
        userspace="abc",
    )
    assert isinstance(session_id, str) and len(session_id) == 36


def test_start_session_stores_running_status(sl):
    pipe = sl._redis.pipeline.return_value
    pipe.execute.return_value = []

    session_id = sl.start_session(
        session_type=SESSION_TYPE_SCHEDULED,
        userspace="ws1",
        agent_config_id="cfg1",
        agent_name="my_agent",
    )

    # First arg to pipe.set should be the key, second should be JSON with status=running
    set_calls = [c for c in pipe.method_calls if c[0] == "set"]
    assert len(set_calls) == 1
    key, payload = set_calls[0][1][0], set_calls[0][1][1]
    assert key == f"session:log:{session_id}"
    doc = json.loads(payload)
    assert doc["status"] == STATUS_RUNNING
    assert doc["session_type"] == SESSION_TYPE_SCHEDULED
    assert doc["userspace"] == "ws1"
    assert doc["agent_config_id"] == "cfg1"


def test_start_session_noop_without_redis(sl_no_redis):
    # Should not raise
    session_id = sl_no_redis.start_session(
        session_type=SESSION_TYPE_CHAT, userspace="ws"
    )
    assert isinstance(session_id, str)


# ---------------------------------------------------------------------------
# finish_session
# ---------------------------------------------------------------------------


def test_finish_session_updates_status(sl, mock_redis):
    # Persist a running session first
    doc = {
        "session_id": "sid1",
        "session_type": SESSION_TYPE_SCHEDULED,
        "userspace": "ws1",
        "started_at": "2026-01-01T00:00:00+00:00",
        "status": STATUS_RUNNING,
        "llm_calls": 0,
        "tool_calls": 0,
        "articles_processed": 0,
    }
    mock_redis.get.return_value = json.dumps(doc)
    pipe = mock_redis.pipeline.return_value
    pipe.execute.return_value = []

    sl.finish_session("sid1", status=STATUS_SUCCESS, llm_calls=2, tool_calls=5)

    set_calls = [c for c in pipe.method_calls if c[0] == "set"]
    assert len(set_calls) == 1
    updated = json.loads(set_calls[0][1][1])
    assert updated["status"] == STATUS_SUCCESS
    assert updated["llm_calls"] == 2
    assert updated["tool_calls"] == 5
    assert updated["finished_at"] is not None
    assert updated["duration_ms"] is not None


def test_finish_session_noop_when_not_found(sl, mock_redis):
    mock_redis.get.return_value = None
    # Should not raise
    sl.finish_session("nonexistent")


def test_finish_session_noop_without_redis(sl_no_redis):
    sl_no_redis.finish_session("sid", status=STATUS_SUCCESS)


# ---------------------------------------------------------------------------
# get_session
# ---------------------------------------------------------------------------


def test_get_session_returns_parsed_doc(sl, mock_redis):
    expected = {"session_id": "s1", "status": STATUS_SUCCESS}
    mock_redis.get.return_value = json.dumps(expected)
    result = sl.get_session("s1")
    assert result == expected
    mock_redis.get.assert_called_once_with("session:log:s1")


def test_get_session_returns_none_when_missing(sl, mock_redis):
    mock_redis.get.return_value = None
    assert sl.get_session("missing") is None


def test_get_session_returns_none_without_redis(sl_no_redis):
    assert sl_no_redis.get_session("any") is None


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


def test_list_sessions_by_userspace(sl, mock_redis):
    mock_redis.zrevrange.return_value = ["s1", "s2"]
    docs = [{"session_id": "s1"}, {"session_id": "s2"}]
    mock_redis.get.side_effect = [json.dumps(d) for d in docs]

    result = sl.list_sessions(userspace="ws1", limit=10, offset=0)

    mock_redis.zrevrange.assert_called_once_with("session:index:ws1", 0, 9)
    assert len(result) == 2


def test_list_sessions_all_without_userspace(sl, mock_redis):
    mock_redis.zrevrange.return_value = []
    sl.list_sessions()
    mock_redis.zrevrange.assert_called_once_with("session:index:all", 0, 49)


def test_list_sessions_returns_empty_without_redis(sl_no_redis):
    assert sl_no_redis.list_sessions() == []


# ---------------------------------------------------------------------------
# context manager
# ---------------------------------------------------------------------------


def test_session_context_success(sl, mock_redis):
    pipe = mock_redis.pipeline.return_value
    pipe.execute.return_value = []
    # For finish_session get
    existing_doc_holder = {}

    def fake_set(key, value, ex=None):
        existing_doc_holder["last"] = value

    def fake_get(key):
        return existing_doc_holder.get("last")

    pipe.set = fake_set
    mock_redis.get.side_effect = lambda k: existing_doc_holder.get("last")

    with sl.session(
        session_type=SESSION_TYPE_CHAT,
        userspace="ws",
    ) as counters:
        counters["llm_calls"] += 1
        counters["tool_calls"] += 3

    # Verify finish was called (last stored doc should have status=success)
    last = existing_doc_holder.get("last")
    if last:
        doc = json.loads(last)
        assert doc["status"] == STATUS_SUCCESS


def test_session_context_marks_error_on_exception(sl, mock_redis):
    pipe = mock_redis.pipeline.return_value
    pipe.execute.return_value = []
    stored = {}

    pipe.set = lambda key, value, ex=None: stored.update({"last": value})
    mock_redis.get.side_effect = lambda k: stored.get("last")

    with pytest.raises(RuntimeError):
        with sl.session(session_type=SESSION_TYPE_SCHEDULED, userspace="ws"):
            raise RuntimeError("boom")

    last = stored.get("last")
    if last:
        doc = json.loads(last)
        assert doc["status"] == STATUS_ERROR
        assert "boom" in (doc.get("error") or "")
