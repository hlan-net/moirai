"""
Tests for MCP tool response standardization.

Validates that all MCP tool functions return the standardized MCPResponse
envelope format (from mcp_service/responses.py), covering success,
validation error, and not-found error cases.

These tests call internal (non-decorated) tool functions directly to avoid
needing a running MCP server, CouchDB, or Redis.
"""

import os

# Set required env vars before any MCP imports
os.environ.setdefault("ADMIN_PASSWORD", "test-password")  # noqa: S105

import pytest
from unittest.mock import patch, MagicMock

# Required envelope fields for all responses
REQUIRED_FIELDS = {"status", "data", "message", "correlation_id", "timestamp", "retryable", "next_action"}
SUCCESS_STATUS = "success"
ERROR_STATUS = "error"


def _assert_envelope(response: dict, expected_status: str = None):
    """Assert response is a valid MCPResponse envelope."""
    assert isinstance(response, dict), f"Expected dict, got {type(response)}"

    missing = REQUIRED_FIELDS - set(response.keys())
    assert not missing, f"Missing envelope fields: {missing}"

    assert response["status"] in ("success", "error", "partial"), (
        f"Invalid status: {response['status']}"
    )
    assert isinstance(response["retryable"], bool)
    assert response["next_action"] in ("none", "retry", "replan", "escalate", "continue")
    assert isinstance(response["correlation_id"], str) and len(response["correlation_id"]) > 0
    assert isinstance(response["timestamp"], str) and "T" in response["timestamp"]

    if expected_status:
        assert response["status"] == expected_status, (
            f"Expected status '{expected_status}', got '{response['status']}': {response.get('message')}"
        )

    if response["status"] == "error":
        assert "error_code" in response, "Error response missing error_code"

    return response


def _assert_success(response: dict) -> dict:
    """Assert success and return data."""
    _assert_envelope(response, SUCCESS_STATUS)
    return response.get("data")


def _assert_error(response: dict, expected_code: str = None) -> dict:
    """Assert error and optionally check error code."""
    _assert_envelope(response, ERROR_STATUS)
    if expected_code:
        assert response.get("error_code") == expected_code
    return response


# ===== Issues Internal Functions =====


class TestIssueInternalResponses:
    """Test issue internal functions return standardized envelopes."""

    @patch("mcp_service.tools.issues.store_doc", return_value="abc123")
    @patch("mcp_service.tools.issues.validate_userspace", return_value=(True, None))
    def test_forge_issue_success(self, mock_validate, mock_store):
        from mcp_service.tools.issues import _forge_issue_internal

        result = _forge_issue_internal(
            logos="Test Event",
            description="Test desc",
            premises=[{"type": "message", "id": "link1"}],
            userspace="00000000-0000-0000-0000-000000000001",
        )
        data = _assert_success(result)
        assert data["issue_id"] == "abc123"
        assert data["logos"] == "Test Event"
        assert data["longevity"] == "transient"

    def test_forge_issue_invalid_userspace(self):
        from mcp_service.tools.issues import _forge_issue_internal

        result = _forge_issue_internal(
            logos="Test",
            description="Test",
            premises=[],
            userspace="not-a-uuid",
        )
        _assert_error(result, "VALIDATION_ERROR")

    @patch("mcp_service.tools.issues.validate_userspace", return_value=(True, None))
    def test_forge_issue_invalid_longevity(self, mock_validate):
        from mcp_service.tools.issues import _forge_issue_internal

        result = _forge_issue_internal(
            logos="Test",
            description="Test",
            premises=[],
            userspace="00000000-0000-0000-0000-000000000001",
            longevity="invalid",
        )
        _assert_error(result, "VALIDATION_ERROR")

    @patch("mcp_service.tools.issues.get_doc", return_value=None)
    @patch("mcp_service.tools.issues.validate_userspace", return_value=(True, None))
    def test_read_issue_not_found(self, mock_validate, mock_get):
        from mcp_service.tools.issues import _read_issue_internal

        result = _read_issue_internal(
            issue_id="nonexistent",
            userspace="00000000-0000-0000-0000-000000000001",
        )
        _assert_error(result, "ISSUE_NOT_FOUND")

    @patch("mcp_service.tools.issues.get_doc", return_value={
        "_id": "abc123",
        "logos": "Test",
        "userspace": "00000000-0000-0000-0000-000000000001",
        "type": "issue",
    })
    @patch("mcp_service.tools.issues.validate_userspace", return_value=(True, None))
    def test_read_issue_success(self, mock_validate, mock_get):
        from mcp_service.tools.issues import _read_issue_internal

        result = _read_issue_internal(
            issue_id="abc123",
            userspace="00000000-0000-0000-0000-000000000001",
        )
        data = _assert_success(result)
        assert data["_id"] == "abc123"

    @patch("mcp_service.tools.issues.delete_doc", return_value=(True, "ok"))
    @patch("mcp_service.tools.issues.get_doc", return_value={
        "_id": "abc123",
        "userspace": "00000000-0000-0000-0000-000000000001",
    })
    @patch("mcp_service.tools.issues.validate_userspace", return_value=(True, None))
    def test_delete_issue_success(self, mock_validate, mock_get, mock_delete):
        from mcp_service.tools.issues import _delete_issue_internal

        result = _delete_issue_internal(
            issue_id="abc123",
            userspace="00000000-0000-0000-0000-000000000001",
        )
        data = _assert_success(result)
        assert data["issue_id"] == "abc123"

    @patch("mcp_service.tools.issues.update_doc", return_value=(True, "ok"))
    @patch("mcp_service.tools.issues.get_doc", return_value={
        "_id": "abc123",
        "userspace": "00000000-0000-0000-0000-000000000001",
        "premises": [],
        "longevity": "transient",
    })
    @patch("mcp_service.tools.issues.validate_userspace", return_value=(True, None))
    def test_measure_issue_success(self, mock_validate, mock_get, mock_update):
        from mcp_service.tools.issues import _measure_issue_internal

        result = _measure_issue_internal(
            issue_id="abc123",
            userspace="00000000-0000-0000-0000-000000000001",
            description="Updated",
        )
        data = _assert_success(result)
        assert "updated_fields" in data


# ===== Search Internal Functions =====


class TestSearchInternalResponses:
    """Test search internal functions return standardized envelopes."""

    def test_search_issues_empty_query(self):
        from mcp_service.tools.search import _search_issues_internal

        result = _search_issues_internal(
            query="   ",
            userspace="00000000-0000-0000-0000-000000000001",
        )
        _assert_error(result, "VALIDATION_ERROR")

    def test_search_issues_invalid_userspace(self):
        from mcp_service.tools.search import _search_issues_internal

        result = _search_issues_internal(
            query="test",
            userspace="bad-uuid",
        )
        _assert_error(result, "VALIDATION_ERROR")


# ===== List Issues Internal =====


class TestListIssuesInternalResponses:
    """Test list issues internal function."""

    @patch("mcp_service.tools.issues.db_request")
    @patch("mcp_service.tools.issues.validate_userspace", return_value=(True, None))
    def test_list_issues_success(self, mock_validate, mock_db):
        from mcp_service.tools.issues import _list_issues_internal

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"docs": []}
        mock_db.return_value = mock_response

        result = _list_issues_internal(
            userspace="00000000-0000-0000-0000-000000000001",
        )
        data = _assert_success(result)
        assert data["issues"] == []
        assert data["count"] == 0

    @patch("mcp_service.tools.issues.db_request")
    @patch("mcp_service.tools.issues.validate_userspace", return_value=(True, None))
    def test_list_issues_db_error(self, mock_validate, mock_db):
        from mcp_service.tools.issues import _list_issues_internal

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_db.return_value = mock_response

        result = _list_issues_internal(
            userspace="00000000-0000-0000-0000-000000000001",
        )
        _assert_error(result)
        assert result["retryable"] is True


# ===== Agent Logic Response Handler =====


class TestAgentLogicResponseHandler:
    """Test that _handle_mcp_response correctly processes standardized envelopes."""

    def test_handles_success_envelope(self):
        from tasks.agent_logic import _handle_mcp_response
        from mcp_service.responses import success

        response = success(
            data={"issue_id": "abc123", "logos": "Test"},
            message="OK",
        ).to_dict()

        ok, data = _handle_mcp_response(response, "test")
        assert ok is True
        assert data["issue_id"] == "abc123"

    def test_handles_error_envelope(self):
        from tasks.agent_logic import _handle_mcp_response
        from mcp_service.responses import validation_error

        response = validation_error("Bad input").to_dict()

        ok, data = _handle_mcp_response(response, "test")
        assert ok is False
        assert data is None

    def test_handles_transient_error_envelope(self):
        from tasks.agent_logic import _handle_mcp_response
        from mcp_service.responses import transient_error

        response = transient_error("DB timeout", retry_after_ms=2000).to_dict()

        ok, data = _handle_mcp_response(response, "test")
        assert ok is False
        assert data is None

    def test_handles_partial_success_envelope(self):
        from tasks.agent_logic import _handle_mcp_response
        from mcp_service.responses import partial_success

        response = partial_success(
            data={"deleted_count": 3, "errors": ["one failed"]},
            message="Partial",
        ).to_dict()

        ok, data = _handle_mcp_response(response, "test")
        assert ok is True
        assert data["deleted_count"] == 3

    def test_handles_legacy_string(self):
        from tasks.agent_logic import _handle_mcp_response

        ok, data = _handle_mcp_response("Issue created OK", "test")
        assert ok is True
        assert data == "Issue created OK"

    def test_handles_legacy_error_string(self):
        from tasks.agent_logic import _handle_mcp_response

        ok, data = _handle_mcp_response("Error: something failed", "test")
        assert ok is False


# ===== Chat Routes Error Detection =====


class TestChatRoutesErrorDetection:
    """Test the JSON-aware error detection in chat_routes.py."""

    def test_detects_error_in_json_envelope(self):
        """Verify JSON envelope error detection works."""
        import json

        result_text = json.dumps({
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": "Bad input",
            "retryable": False,
            "next_action": "replan",
        })

        # Simulate the detection logic from chat_routes.py
        result_is_error = False
        try:
            parsed = json.loads(result_text)
            if isinstance(parsed, dict) and parsed.get("status") == "error":
                result_is_error = True
        except (json.JSONDecodeError, ValueError):
            if result_text.strip().lower().startswith("error"):
                result_is_error = True

        assert result_is_error is True

    def test_detects_success_in_json_envelope(self):
        """Verify JSON envelope success is not flagged as error."""
        import json

        result_text = json.dumps({
            "status": "success",
            "data": {"feed_id": "abc"},
            "message": "OK",
        })

        result_is_error = False
        try:
            parsed = json.loads(result_text)
            if isinstance(parsed, dict) and parsed.get("status") == "error":
                result_is_error = True
        except (json.JSONDecodeError, ValueError):
            if result_text.strip().lower().startswith("error"):
                result_is_error = True

        assert result_is_error is False

    def test_detects_legacy_error_string(self):
        """Verify legacy string error detection still works."""
        result_text = "Error: something went wrong"

        result_is_error = False
        try:
            parsed = __import__("json").loads(result_text)
            if isinstance(parsed, dict) and parsed.get("status") == "error":
                result_is_error = True
        except (ValueError,):
            if result_text.strip().lower().startswith("error"):
                result_is_error = True

        assert result_is_error is True
