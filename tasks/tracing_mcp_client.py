"""Tracing wrapper for MCP client that records step-level traces.

Transparently proxies ``call_tool()`` on the underlying MCP client while
recording each invocation as a step in the session logger.  Logic modules
receive this wrapper instead of the raw client and need no code changes.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from tasks.session_logger import SessionLogger

logger = logging.getLogger(__name__)

# Tools whose execution has side-effects that are difficult or impossible to
# reverse.  Used to tag steps with ``risk_level = "destructive"`` and to gate
# execution behind the approval workflow when ``require_approval`` is enabled.
DESTRUCTIVE_TOOLS: frozenset[str] = frozenset(
    {
        "delete_issue",
        "delete_event",
        "delete_trend",
        "delete_feed",
        "delete_stale_entities",
        "publish_to_bluesky",
        "delete_user",
    }
)

_MAX_SUMMARY_LEN = 500

# Redis key prefixes for the approval workflow
_APPROVAL_PENDING_PREFIX = "approval:pending:"
_APPROVAL_DECISION_PREFIX = "approval:decision:"
_APPROVAL_QUEUE_PREFIX = "approval:queue:"
_SESSION_CANCEL_PREFIX = "session:cancel:"
_APPROVAL_TTL = 600  # seconds


class AgentCancelledException(Exception):
    """Raised when an operator cancels a running agent session."""


def _truncate(value: str, max_len: int = _MAX_SUMMARY_LEN) -> str:
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


class TracingMCPClient:
    """Wrapper that intercepts ``call_tool`` to record step-level traces.

    Parameters
    ----------
    mcp_client
        The real MCP client (or any object with a ``call_tool`` method).
    session_logger
        A :class:`SessionLogger` instance for persisting steps.
    session_id
        The session ID to attach steps to.
    redis_client
        Optional Redis client for approval gate and cancellation checks.
    max_retries
        Maximum number of automatic retries for transient (``retryable``) tool
        failures.  ``1`` means no retries (single attempt).
    require_approval
        When ``True``, destructive tool calls pause and wait for human
        approval via Redis before executing.
    approval_timeout
        Seconds to wait for an approval decision before timing out.
    userspace
        The userspace UUID for this agent run (used in approval requests).
    agent_name
        Human-readable agent name for approval request context.
    """

    def __init__(
        self,
        mcp_client: Any,
        session_logger: SessionLogger,
        session_id: str,
        *,
        redis_client: Any = None,
        max_retries: int = 3,
        require_approval: bool = False,
        approval_timeout: int = 300,
        userspace: str = "",
        agent_name: str = "",
    ) -> None:
        self._inner = mcp_client
        self._session_logger = session_logger
        self._session_id = session_id
        self._redis = redis_client
        self._max_retries = max_retries
        self._require_approval = require_approval
        self._approval_timeout = approval_timeout
        self._userspace = userspace
        self._agent_name = agent_name

    # Expose logger/session_id so agent_logic can opt-in to LLM tracing
    @property
    def session_logger(self) -> SessionLogger:
        return self._session_logger

    @property
    def session_id(self) -> str:
        return self._session_id

    # ------------------------------------------------------------------
    # Cancellation check
    # ------------------------------------------------------------------

    def _check_cancelled(self) -> None:
        """Raise if the session has been cancelled by an operator."""
        if self._redis:
            try:
                if self._redis.get(f"{_SESSION_CANCEL_PREFIX}{self._session_id}"):
                    raise AgentCancelledException(
                        f"Agent session {self._session_id} cancelled by operator"
                    )
            except AgentCancelledException:
                raise
            except Exception:
                # Don't let Redis errors block execution
                logger.debug("Could not check cancellation flag", exc_info=True)

    # ------------------------------------------------------------------
    # Approval gate
    # ------------------------------------------------------------------

    def _request_approval(self, tool_name: str, kwargs: dict) -> str:
        """Submit an approval request and poll for a decision.

        Returns ``"approved"``, ``"denied"``, or ``"timeout"``.
        """
        request_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Write the pending request
        pending_key = f"{_APPROVAL_PENDING_PREFIX}{request_id}"
        self._redis.hset(
            pending_key,
            mapping={
                "request_id": request_id,
                "session_id": self._session_id,
                "tool_name": tool_name,
                "input_summary": _truncate(str(kwargs)),
                "risk_level": "destructive",
                "requested_at": now,
                "agent_name": self._agent_name,
                "userspace": self._userspace,
            },
        )
        self._redis.expire(pending_key, _APPROVAL_TTL)

        # Add to per-userspace queue for listing
        queue_key = f"{_APPROVAL_QUEUE_PREFIX}{self._userspace}"
        self._redis.lpush(queue_key, request_id)
        self._redis.expire(queue_key, _APPROVAL_TTL)

        # Record pending step
        self._session_logger.add_step(
            self._session_id,
            {
                "step_id": str(uuid.uuid4()),
                "step_type": "tool_call",
                "tool_name": tool_name,
                "input_summary": _truncate(str(kwargs)),
                "status": "pending_approval",
                "risk_level": "destructive",
                "correlation_id": request_id,
                "attempt": 0,
                "timestamp": now,
            },
        )

        logger.info(
            "Approval requested for %s (request_id=%s, agent=%s)",
            tool_name,
            request_id,
            self._agent_name,
        )

        # Poll for decision
        decision_key = f"{_APPROVAL_DECISION_PREFIX}{request_id}"
        deadline = time.monotonic() + self._approval_timeout
        while time.monotonic() < deadline:
            decision = self._redis.get(decision_key)
            if decision:
                if isinstance(decision, bytes):
                    decision = decision.decode("utf-8")
                logger.info(
                    "Approval decision for %s: %s (request_id=%s)",
                    tool_name,
                    decision,
                    request_id,
                )
                return decision
            # Also check for session cancellation while waiting
            self._check_cancelled()
            time.sleep(1.0)

        logger.warning(
            "Approval timed out for %s (request_id=%s, timeout=%ds)",
            tool_name,
            request_id,
            self._approval_timeout,
        )
        return "timeout"

    # ------------------------------------------------------------------
    # Approval rejection helpers
    # ------------------------------------------------------------------

    def _record_rejection(
        self, tool_name: str, kwargs: dict, error_code: str, message: str,
    ) -> dict:
        """Record a denied/timeout step and return an error MCPResponse."""
        step = {
            "step_id": str(uuid.uuid4()),
            "step_type": "tool_call",
            "tool_name": tool_name,
            "input_summary": _truncate(str(kwargs)),
            "status": "denied",
            "risk_level": "destructive",
            "error_code": error_code,
            "error_message": message,
            "correlation_id": str(uuid.uuid4()),
            "attempt": 0,
            "latency_ms": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._session_logger.add_step(self._session_id, step)
        return {
            "status": "error",
            "error_code": error_code,
            "message": message,
            "retryable": False,
        }

    # ------------------------------------------------------------------
    # Proxied call_tool with tracing + approval + retry
    # ------------------------------------------------------------------

    def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Call a tool on the inner client, recording a step trace for each attempt."""
        # Check for cancellation before each tool call
        self._check_cancelled()

        risk_level = "destructive" if tool_name in DESTRUCTIVE_TOOLS else "normal"

        # Approval gate for destructive tools
        if self._require_approval and risk_level == "destructive" and self._redis:
            decision = self._request_approval(tool_name, kwargs)
            if decision == "denied":
                return self._record_rejection(
                    tool_name, kwargs,
                    "APPROVAL_DENIED", "Destructive action denied by operator",
                )
            if decision == "timeout":
                return self._record_rejection(
                    tool_name, kwargs,
                    "APPROVAL_TIMEOUT",
                    f"No approval received within {self._approval_timeout}s",
                )
            # "approved" — fall through to execute

        last_result = None
        for attempt in range(1, self._max_retries + 1):
            correlation_id = str(uuid.uuid4())
            start = time.monotonic()
            step: dict[str, Any] = {
                "step_id": str(uuid.uuid4()),
                "step_type": "tool_call",
                "tool_name": tool_name,
                "input_summary": _truncate(str(kwargs)),
                "correlation_id": correlation_id,
                "attempt": attempt,
                "risk_level": risk_level,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            try:
                result = self._inner.call_tool(tool_name, **kwargs)
                latency_ms = int((time.monotonic() - start) * 1000)
                step["latency_ms"] = latency_ms

                # Parse MCPResponse envelope if present
                if isinstance(result, dict):
                    step["correlation_id"] = result.get(
                        "correlation_id", correlation_id
                    )
                    if result.get("status") == "error":
                        step["status"] = "error"
                        step["error_code"] = result.get("error_code")
                        step["error_message"] = result.get("message")
                        step["output_summary"] = _truncate(
                            result.get("message") or str(result.get("data"))
                        )

                        # Retry transient errors
                        if result.get("retryable") and attempt < self._max_retries:
                            step["status"] = "retried"
                            self._session_logger.add_step(self._session_id, step)
                            retry_after_ms = result.get("retry_after_ms", 1000)
                            time.sleep(retry_after_ms / 1000.0)
                            last_result = result
                            continue
                    else:
                        step["status"] = "success"
                        step["output_summary"] = _truncate(
                            str(result.get("data", ""))
                        )
                else:
                    step["status"] = "success"
                    step["output_summary"] = _truncate(str(result))

                self._session_logger.add_step(self._session_id, step)
                return result

            except Exception as exc:
                latency_ms = int((time.monotonic() - start) * 1000)
                step["latency_ms"] = latency_ms
                step["status"] = "error"
                step["error_message"] = str(exc)
                step["output_summary"] = _truncate(str(exc))
                self._session_logger.add_step(self._session_id, step)
                raise

        # All retries exhausted — return last result
        return last_result

    # ------------------------------------------------------------------
    # Proxy everything else to the inner client
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
