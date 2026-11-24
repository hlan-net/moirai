"""The MCP SDK 2.x surface the code depends on, checked with real SDK objects."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

os.environ.setdefault("ADMIN_PASSWORD", "test-password")

import httpx2  # noqa: E402
from mcp import types  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402


def test_server_is_an_mcpserver_with_the_tools_registered():
    from mcp_service import main  # noqa: F401  (imports the tool modules)
    from mcp_service.tools import feeds

    # The instance the tool modules registered on. Other test modules reload
    # mcp_service.core, so ``mcp_service.core.mcp`` may be a fresh, empty one.
    mcp = feeds.mcp
    assert isinstance(mcp, MCPServer)
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert {"add_feed", "list_feeds", "read_feed", "update_feed_category"} <= names
    # 2.x validates results against the protocol schema: every tool's input
    # schema must be an object schema or tools/list fails for all of them.
    assert all(t.input_schema.get("type") == "object" for t in tools)


def test_sse_app_serves_the_sse_endpoints_and_the_health_route():
    from mcp_service.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert {"/sse", "/messages", "/health"} <= {p.rstrip("/") for p in paths if p}


def test_openai_tool_conversion_reads_the_snake_case_schema_field():
    with patch.dict("sys.modules"):
        from api import chat_routes

    tool = types.Tool(
        name="list_feeds",
        description="List feeds",
        input_schema={
            "type": "object",
            "properties": {"userspace": {"type": "string"}},
        },
    )
    converted = chat_routes._convert_to_openai_tools(
        types.ListToolsResult(tools=[tool])
    )
    assert converted[0]["function"]["name"] == "list_feeds"
    assert converted[0]["function"]["parameters"]["properties"] == {
        "userspace": {"type": "string"}
    }


def test_tool_result_error_flag_is_snake_case():
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text="boom")], is_error=True
    )
    assert result.is_error is True
    assert result.content[0].text == "boom"


def test_http_client_factory_returns_an_httpx2_client():
    from api import chat_routes

    async def make() -> None:
        client = chat_routes._create_http_client(headers={"Host": "localhost:8090"})
        try:
            assert isinstance(client, httpx2.AsyncClient)
            assert client.headers["Host"] == "localhost:8090"
        finally:
            await client.aclose()

    asyncio.run(make())


def _server_with_sample_tools() -> MCPServer:
    server = MCPServer("test")

    @server.tool()
    def echo(name: str, userspace: str = "") -> dict:
        return {"status": "success", "data": {"name": name, "userspace": userspace}}

    @server.tool()
    def plain() -> str:
        return "not json"

    @server.tool()
    def crash() -> dict:
        raise RuntimeError("database on fire")

    return server


def test_in_process_client_returns_the_tools_own_dict():
    from mcp_service.local_client import InProcessMCPClient

    client = InProcessMCPClient(_server_with_sample_tools())
    assert client.call_tool("echo", name="n", userspace="u") == {
        "status": "success",
        "data": {"name": "n", "userspace": "u"},
    }
    assert client.call_tool("plain") == "not json"


def test_in_process_client_reports_sdk_failures_as_error_envelopes():
    from mcp_service.local_client import InProcessMCPClient

    client = InProcessMCPClient(_server_with_sample_tools())

    unknown = client.call_tool("no_such_tool")
    assert unknown["status"] == "error"
    assert unknown["error_code"] == "VALIDATION_ERROR"
    assert unknown["retryable"] is False

    invalid = client.call_tool("echo")  # required 'name' missing
    assert invalid["status"] == "error"
    assert invalid["error_code"] == "VALIDATION_ERROR"

    crashed = client.call_tool("crash")
    assert crashed["status"] == "error"
    assert crashed["error_code"] == "UNEXPECTED_ERROR"
    assert "database on fire" in crashed["message"]


def test_agent_tool_calls_reach_a_tool_through_the_tracing_client():
    """The path agent logic uses: TracingMCPClient -> in-process client -> tool."""
    from unittest.mock import MagicMock

    from mcp_service.local_client import InProcessMCPClient
    from tasks.tracing_mcp_client import TracingMCPClient

    session_logger = MagicMock()
    client = TracingMCPClient(
        mcp_client=InProcessMCPClient(_server_with_sample_tools()),
        session_logger=session_logger,
        session_id="s-1",
    )
    result = client.call_tool("echo", name="n", userspace="u")
    assert result["data"] == {"name": "n", "userspace": "u"}
    step = session_logger.add_step.call_args.args[1]
    assert step["tool_name"] == "echo"
    assert step["status"] == "success"


def test_orchestrator_is_given_the_in_process_client():
    from mcp_service import main
    from mcp_service.local_client import InProcessMCPClient

    assert isinstance(main.agent_orchestrator.mcp_client, InProcessMCPClient)
