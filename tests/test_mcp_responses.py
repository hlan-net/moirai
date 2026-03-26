"""
Tests for MCP standardized response envelope.

Validates the response contract defined in TODO_0.7.1.md #1.
"""

import json
from mcp_service.responses import (
    MCPStatus,
    MCPErrorCode,
    NextAction,
    success,
    error,
    validation_error,
    not_found_error,
    transient_error,
    conflict_error,
    internal_error,
    partial_success,
    wrap_legacy_response,
)


class TestMCPResponseEnvelope:
    """Test the core MCPResponse class."""
    
    def test_success_response_structure(self):
        """Success response has correct structure."""
        resp = success(
            data={"feed_id": "abc123", "title": "Test Feed"},
            message="Feed added successfully"
        )
        
        assert resp.status == MCPStatus.SUCCESS
        assert resp.data == {"feed_id": "abc123", "title": "Test Feed"}
        assert resp.message == "Feed added successfully"
        assert resp.error_code is None
        assert resp.retryable is False
        assert resp.next_action == NextAction.NONE
        assert resp.correlation_id is not None
        assert resp.timestamp is not None
    
    def test_success_response_to_dict(self):
        """Success response converts to dict correctly."""
        resp = success(
            data={"key": "value"},
            message="Operation successful"
        )
        
        d = resp.to_dict()
        
        assert d["status"] == "success"
        assert d["data"] == {"key": "value"}
        assert d["message"] == "Operation successful"
        assert d["retryable"] is False
        assert d["next_action"] == "none"
        assert "correlation_id" in d
        assert "timestamp" in d
        assert "error_code" not in d
    
    def test_error_response_structure(self):
        """Error response has correct structure."""
        resp = error(
            error_code=MCPErrorCode.VALIDATION_ERROR,
            message="Invalid parameter",
            retryable=False,
            next_action=NextAction.REPLAN
        )
        
        assert resp.status == MCPStatus.ERROR
        assert resp.error_code == MCPErrorCode.VALIDATION_ERROR
        assert resp.message == "Invalid parameter"
        assert resp.retryable is False
        assert resp.next_action == NextAction.REPLAN
    
    def test_retryable_error_includes_retry_metadata(self):
        """Retryable errors include retry guidance."""
        resp = transient_error(
            message="Network timeout",
            retry_after_ms=1000,
            max_retries=3
        )
        
        d = resp.to_dict()
        
        assert d["status"] == "error"
        assert d["error_code"] == "TRANSIENT_NETWORK"
        assert d["retryable"] is True
        assert d["next_action"] == "retry"
        assert d["retry_after_ms"] == 1000
        assert d["max_retries_hint"] == 3


class TestErrorCodeMapping:
    """Test canonical error code helpers."""
    
    def test_validation_error(self):
        """Validation errors are non-retryable."""
        resp = validation_error("Missing required field")
        
        assert resp.status == MCPStatus.ERROR
        assert resp.error_code == MCPErrorCode.VALIDATION_ERROR
        assert resp.retryable is False
        assert resp.next_action == NextAction.REPLAN
    
    def test_not_found_error_feed(self):
        """Not found errors map to specific resource types."""
        resp = not_found_error("feed", "feed-123")
        
        assert resp.status == MCPStatus.ERROR
        assert resp.error_code == MCPErrorCode.FEED_NOT_FOUND
        assert resp.retryable is False
        assert "feed-123" in resp.message
    
    def test_not_found_error_issue(self):
        """Issue not found uses correct error code."""
        resp = not_found_error("issue", "issue-456")
        
        assert resp.error_code == MCPErrorCode.ISSUE_NOT_FOUND
    
    def test_transient_error_is_retryable(self):
        """Transient errors are retryable."""
        resp = transient_error("Database unavailable")
        
        assert resp.status == MCPStatus.ERROR
        assert resp.error_code == MCPErrorCode.TRANSIENT_NETWORK
        assert resp.retryable is True
        assert resp.next_action == NextAction.RETRY
        assert resp.retry_after_ms is not None
    
    def test_conflict_error_is_retryable(self):
        """Conflict errors are retryable."""
        resp = conflict_error("Document revision mismatch")
        
        assert resp.error_code == MCPErrorCode.CONFLICT_REVISION
        assert resp.retryable is True
        assert resp.next_action == NextAction.RETRY
    
    def test_internal_error_escalates(self):
        """Internal errors suggest escalation."""
        resp = internal_error("Unexpected database state")
        
        assert resp.error_code == MCPErrorCode.INTERNAL_ERROR
        assert resp.retryable is False
        assert resp.next_action == NextAction.ESCALATE


class TestPartialSuccess:
    """Test partial success responses."""
    
    def test_partial_success_structure(self):
        """Partial success has correct status."""
        resp = partial_success(
            data={"succeeded": 3, "failed": 1},
            message="3 of 4 operations completed",
            next_action=NextAction.CONTINUE
        )
        
        assert resp.status == MCPStatus.PARTIAL
        assert resp.data == {"succeeded": 3, "failed": 1}
        assert resp.next_action == NextAction.CONTINUE


class TestLegacyWrapper:
    """Test wrapping legacy string responses."""
    
    def test_wrap_success_string(self):
        """Success strings are wrapped correctly."""
        resp = wrap_legacy_response("Feed added with ID: abc123")
        
        assert resp.status == MCPStatus.SUCCESS
        assert "Feed added" in resp.message
    
    def test_wrap_error_not_found(self):
        """Not found errors are detected."""
        resp = wrap_legacy_response("Error: Feed not found or access denied")
        
        assert resp.status == MCPStatus.ERROR
        assert resp.retryable is False
    
    def test_wrap_error_validation(self):
        """Validation errors are detected."""
        resp = wrap_legacy_response("Error: Invalid userspace UUID")
        
        assert resp.status == MCPStatus.ERROR
        assert resp.error_code == MCPErrorCode.VALIDATION_ERROR
    
    def test_wrap_error_duplicate(self):
        """Duplicate resource errors are detected."""
        resp = wrap_legacy_response("Feed already exists in userspace abc")
        
        assert resp.status == MCPStatus.ERROR
        assert resp.error_code == MCPErrorCode.DUPLICATE_RESOURCE


class TestCorrelationID:
    """Test correlation ID handling."""
    
    def test_auto_generated_correlation_id(self):
        """Correlation IDs are auto-generated if not provided."""
        resp = success(data={"key": "value"})
        
        assert resp.correlation_id is not None
        assert len(resp.correlation_id) > 0
    
    def test_custom_correlation_id(self):
        """Custom correlation IDs are preserved."""
        custom_id = "custom-trace-id-12345"
        resp = success(data={"key": "value"}, correlation_id=custom_id)
        
        assert resp.correlation_id == custom_id
    
    def test_correlation_id_in_dict(self):
        """Correlation ID is included in dict output."""
        resp = success(data={}, correlation_id="test-id")
        d = resp.to_dict()
        
        assert d["correlation_id"] == "test-id"


class TestJSONSerialization:
    """Test JSON serialization."""
    
    def test_to_json_string(self):
        """Response can be serialized to JSON."""
        resp = success(
            data={"feed_id": "123"},
            message="Feed added"
        )
        
        json_str = resp.to_json_string()
        parsed = json.loads(json_str)
        
        assert parsed["status"] == "success"
        assert parsed["data"]["feed_id"] == "123"
        assert parsed["message"] == "Feed added"
    
    def test_json_serialization_with_error(self):
        """Error responses serialize correctly."""
        resp = validation_error("Bad input")
        json_str = resp.to_json_string()
        parsed = json.loads(json_str)
        
        assert parsed["status"] == "error"
        assert parsed["error_code"] == "VALIDATION_ERROR"
        assert parsed["retryable"] is False


class TestRetryGuidance:
    """Test retry guidance metadata."""
    
    def test_non_retryable_has_no_retry_metadata(self):
        """Non-retryable errors don't include retry hints."""
        resp = validation_error("Bad input")
        d = resp.to_dict()
        
        assert d["retryable"] is False
        assert "retry_after_ms" not in d
    
    def test_retryable_includes_retry_delay(self):
        """Retryable errors include retry delay."""
        resp = transient_error("Timeout", retry_after_ms=5000)
        d = resp.to_dict()
        
        assert d["retryable"] is True
        assert d["retry_after_ms"] == 5000
        assert d["max_retries_hint"] == 3  # default
    
    def test_custom_max_retries(self):
        """Max retries hint can be customized."""
        resp = transient_error("Rate limited", max_retries=10)
        d = resp.to_dict()
        
        assert d["max_retries_hint"] == 10


class TestNextActionGuidance:
    """Test next_action suggestions."""
    
    def test_success_next_action_none(self):
        """Successful operations have no next action."""
        resp = success(data={})
        assert resp.next_action == NextAction.NONE
    
    def test_validation_error_suggests_replan(self):
        """Validation errors suggest replanning."""
        resp = validation_error("Bad input")
        assert resp.next_action == NextAction.REPLAN
    
    def test_transient_error_suggests_retry(self):
        """Transient errors suggest retry."""
        resp = transient_error("Network timeout")
        assert resp.next_action == NextAction.RETRY
    
    def test_internal_error_suggests_escalate(self):
        """Internal errors suggest escalation."""
        resp = internal_error("Unexpected state")
        assert resp.next_action == NextAction.ESCALATE
    
    def test_partial_success_suggests_continue(self):
        """Partial success suggests continuing."""
        resp = partial_success(
            data={"done": 5, "pending": 3},
            message="Batch partially complete"
        )
        assert resp.next_action == NextAction.CONTINUE
