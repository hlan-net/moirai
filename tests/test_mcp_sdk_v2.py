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
