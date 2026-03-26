"""
Standardized MCP Tool Response Envelope

This module defines the canonical response format for all MCP tools,
ensuring consistent error handling, retry guidance, and observability.

See TODO_0.7.1.md #1 for requirements.
"""

from enum import Enum
from typing import Any, Optional
from datetime import datetime, timezone
import uuid


class MCPStatus(str, Enum):
    """Status codes for MCP tool responses."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"  # Some operations succeeded, others failed


class MCPErrorCode(str, Enum):
    """Canonical error codes for MCP tool failures."""
    
    # Validation errors (4xx-equivalent)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_USERSPACE = "INVALID_USERSPACE"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    
    # Not found errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    FEED_NOT_FOUND = "FEED_NOT_FOUND"
    ISSUE_NOT_FOUND = "ISSUE_NOT_FOUND"
    ARTICLE_NOT_FOUND = "ARTICLE_NOT_FOUND"
    
    # Conflict errors
    CONFLICT_REVISION = "CONFLICT_REVISION"
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
    
    # Transient errors (5xx-equivalent, retryable)
    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    
    # Internal errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


class NextAction(str, Enum):
    """Suggested next action for the agent runtime."""
    NONE = "none"  # Task complete, no further action needed
    RETRY = "retry"  # Retry the same operation
    REPLAN = "replan"  # Failure requires replanning
    ESCALATE = "escalate"  # Human intervention needed
    CONTINUE = "continue"  # Partial success, continue with next step


class MCPResponse:
    """
    Standardized response envelope for all MCP tools.
    
    Attributes:
        status: success, error, or partial
        data: The actual response data (None on error)
        error_code: Canonical error code (None on success)
        message: Human-readable message
        retryable: Whether the operation can be retried
        next_action: Suggested next action for agent runtime
        correlation_id: Unique ID for request tracing
        retry_after_ms: Suggested retry delay in milliseconds
        max_retries_hint: Suggested maximum retries before giving up
    """
    
    def __init__(
        self,
        status: MCPStatus,
        data: Optional[Any] = None,
        error_code: Optional[MCPErrorCode] = None,
        message: str = "",
        retryable: bool = False,
        next_action: NextAction = NextAction.NONE,
        correlation_id: Optional[str] = None,
        retry_after_ms: Optional[int] = None,
        max_retries_hint: int = 3,
    ):
        self.status = status
        self.data = data
        self.error_code = error_code
        self.message = message
        self.retryable = retryable
        self.next_action = next_action
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.retry_after_ms = retry_after_ms
        self.max_retries_hint = max_retries_hint
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> dict:
        """Convert response to dictionary for JSON serialization."""
        result = {
            "status": self.status.value,
            "data": self.data,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
        }
        
        if self.error_code:
            result["error_code"] = self.error_code.value
        
        if self.retryable:
            result["retryable"] = True
            result["next_action"] = self.next_action.value
            if self.retry_after_ms:
                result["retry_after_ms"] = self.retry_after_ms
            result["max_retries_hint"] = self.max_retries_hint
        else:
            result["retryable"] = False
            result["next_action"] = self.next_action.value
        
        return result
    
    def to_json_string(self) -> str:
        """Convert response to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=2)


# --- Convenience factory methods ---

def success(data: Any, message: str = "", correlation_id: Optional[str] = None) -> MCPResponse:
    """Create a success response."""
    return MCPResponse(
        status=MCPStatus.SUCCESS,
        data=data,
        message=message,
        next_action=NextAction.NONE,
        correlation_id=correlation_id,
    )


def error(
    error_code: MCPErrorCode,
    message: str,
    retryable: bool = False,
    next_action: NextAction = NextAction.REPLAN,
    retry_after_ms: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> MCPResponse:
    """Create an error response."""
    return MCPResponse(
        status=MCPStatus.ERROR,
        error_code=error_code,
        message=message,
        retryable=retryable,
        next_action=next_action,
        retry_after_ms=retry_after_ms,
        correlation_id=correlation_id,
    )


def validation_error(message: str, correlation_id: Optional[str] = None) -> MCPResponse:
    """Create a validation error response (non-retryable)."""
    return error(
        error_code=MCPErrorCode.VALIDATION_ERROR,
        message=message,
        retryable=False,
        next_action=NextAction.REPLAN,
        correlation_id=correlation_id,
    )


def not_found_error(resource_type: str, resource_id: str, correlation_id: Optional[str] = None) -> MCPResponse:
    """Create a resource not found error response."""
    error_codes = {
        "feed": MCPErrorCode.FEED_NOT_FOUND,
        "issue": MCPErrorCode.ISSUE_NOT_FOUND,
        "article": MCPErrorCode.ARTICLE_NOT_FOUND,
    }
    code = error_codes.get(resource_type, MCPErrorCode.RESOURCE_NOT_FOUND)
    
    return error(
        error_code=code,
        message=f"{resource_type.capitalize()} '{resource_id}' not found or access denied",
        retryable=False,
        next_action=NextAction.REPLAN,
        correlation_id=correlation_id,
    )


def transient_error(
    message: str,
    retry_after_ms: int = 1000,
    max_retries: int = 3,
    correlation_id: Optional[str] = None,
) -> MCPResponse:
    """Create a transient error response (retryable)."""
    return MCPResponse(
        status=MCPStatus.ERROR,
        error_code=MCPErrorCode.TRANSIENT_NETWORK,
        message=message,
        retryable=True,
        next_action=NextAction.RETRY,
        retry_after_ms=retry_after_ms,
        max_retries_hint=max_retries,
        correlation_id=correlation_id,
    )


def conflict_error(message: str, correlation_id: Optional[str] = None) -> MCPResponse:
    """Create a conflict error response (retryable with fresh fetch)."""
    return error(
        error_code=MCPErrorCode.CONFLICT_REVISION,
        message=message,
        retryable=True,
        next_action=NextAction.RETRY,
        retry_after_ms=500,
        correlation_id=correlation_id,
    )


def internal_error(message: str, correlation_id: Optional[str] = None) -> MCPResponse:
    """Create an internal error response (non-retryable)."""
    return error(
        error_code=MCPErrorCode.INTERNAL_ERROR,
        message=message,
        retryable=False,
        next_action=NextAction.ESCALATE,
        correlation_id=correlation_id,
    )


def partial_success(
    data: Any,
    message: str,
    next_action: NextAction = NextAction.CONTINUE,
    correlation_id: Optional[str] = None,
) -> MCPResponse:
    """Create a partial success response (some operations succeeded)."""
    return MCPResponse(
        status=MCPStatus.PARTIAL,
        data=data,
        message=message,
        next_action=next_action,
        correlation_id=correlation_id,
    )


# --- Helper for wrapping existing string-based tools ---

def wrap_legacy_response(legacy_response: str, correlation_id: Optional[str] = None) -> MCPResponse:
    """
    Wrap a legacy string response in the standardized envelope.
    
    This is a temporary helper to gradually migrate existing tools.
    Detects error patterns in the string and maps to appropriate response types.
    
    Args:
        legacy_response: The old-style string response
        correlation_id: Optional correlation ID for tracing
        
    Returns:
        MCPResponse with best-effort classification
    """
    lower = legacy_response.lower()
    
    # Error detection patterns - check specific errors before generic "error" keyword
    
    # Check for duplicate/already exists (may not contain "error" keyword)
    if "already exists" in lower or "duplicate" in lower:
        return error(
            error_code=MCPErrorCode.DUPLICATE_RESOURCE,
            message=legacy_response,
            retryable=False,
            next_action=NextAction.REPLAN,
            correlation_id=correlation_id,
        )
    
    # Check for explicit "error" keyword
    if "error" in lower:
        if "not found" in lower or "denied" in lower:
            return not_found_error("resource", "unknown", correlation_id)
        elif "invalid" in lower or "validation" in lower:
            return validation_error(legacy_response, correlation_id)
        else:
            return internal_error(legacy_response, correlation_id)
    
    # Success - treat as data
    return success(
        data={"message": legacy_response},
        message=legacy_response,
        correlation_id=correlation_id,
    )
