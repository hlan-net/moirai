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
DESTRUCTIVE_TOOLS: set[str] = frozenset(
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
    max_retries
        Maximum number of automatic retries for transient (``retryable``) tool
        failures.  ``0`` disables retries.
    """

    def __init__(
        self,
        mcp_client: Any,
        session_logger: SessionLogger,
        session_id: str,
        *,
        max_retries: int = 3,
    ) -> None:
        self._inner = mcp_client
        self._session_logger = session_logger
        self._session_id = session_id
        self._max_retries = max_retries

    # Expose logger/session_id so agent_logic can opt-in to LLM tracing
    @property
    def session_logger(self) -> SessionLogger:
        return self._session_logger

    @property
    def session_id(self) -> str:
        return self._session_id

    # ------------------------------------------------------------------
    # Proxied call_tool with tracing + retry
    # ------------------------------------------------------------------

    def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Call a tool on the inner client, recording a step trace for each attempt."""
        risk_level = "destructive" if tool_name in DESTRUCTIVE_TOOLS else "normal"

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
