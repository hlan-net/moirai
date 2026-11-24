"""In-process MCP client for agent logic.

Agent logic calls tools as ``mcp_client.call_tool("name", key=value)`` and reads
the tool's own return value, the ``MCPResponse`` dict. The SDK server object does
not have that interface: ``MCPServer.call_tool`` is a coroutine that takes the
arguments as one dict and returns a protocol ``CallToolResult``. This adapter
bridges the two, so that agents run tools in the server's own process, through
the SDK's argument validation, without a network round trip.
"""

import asyncio
import json
import logging
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.types import CallToolResult, TextContent

from mcp_service.responses import MCPErrorCode, NextAction, error

logger = logging.getLogger(__name__)


class InProcessMCPClient:
    """Synchronous ``call_tool(name, **kwargs)`` on top of an ``MCPServer``.

    Meant for threads that have no running event loop, such as the agent
    orchestrator's: each call runs the server coroutine to completion with
    ``asyncio.run``.
    """

    def __init__(self, server: MCPServer) -> None:
        self._server = server

    def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Run a tool and return what the tool function returned.

        Failures the SDK raises (unknown tool, invalid arguments, an exception
        inside the tool) come back as an error ``MCPResponse`` dict, the same
        shape a tool uses to report its own errors.
        """
        try:
            result = asyncio.run(self._server.call_tool(tool_name, kwargs))
        except UnexpectedToolError as exc:
            # The tool itself raised; the original exception is the cause.
            logger.exception("Tool '%s' raised", tool_name)
            return error(
                MCPErrorCode.UNEXPECTED_ERROR,
                f"{exc}: {exc.__cause__}" if exc.__cause__ else str(exc),
                next_action=NextAction.ESCALATE,
            ).to_dict()
        except ToolError as exc:
            # Unknown tool or arguments that fail the tool's schema.
            return error(
                MCPErrorCode.VALIDATION_ERROR,
                str(exc),
                next_action=NextAction.REPLAN,
            ).to_dict()

        if not isinstance(result, CallToolResult):
            return error(
                MCPErrorCode.UNEXPECTED_ERROR,
                f"Tool '{tool_name}' asked for input, which agents cannot give",
                next_action=NextAction.ESCALATE,
            ).to_dict()

        value = _unwrap(result)
        if result.is_error and not _is_envelope(value):
            return error(
                MCPErrorCode.UNEXPECTED_ERROR,
                str(value),
                next_action=NextAction.ESCALATE,
            ).to_dict()
        return value


def _is_envelope(value: Any) -> bool:
    return isinstance(value, dict) and "status" in value


def _unwrap(result: CallToolResult) -> Any:
    """Recover the tool's return value from the protocol result.

    The SDK serializes a returned dict to JSON in one text block; other return
    types arrive as plain text, one block per item.
    """
    texts = [c.text for c in result.content if isinstance(c, TextContent)]
    if len(texts) != 1:
        return texts
    try:
        return json.loads(texts[0])
    except ValueError:
        return texts[0]
