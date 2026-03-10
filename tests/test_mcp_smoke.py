"""MCP smoke tests for tools beyond basic CRUD.

Covers: list_feeds, search, user management, annotations, staleness,
and agent config tools. Requires a running MCP server.
"""

import os
import base64
import json
import pytest
from mcp.client.sse import sse_client
from mcp import ClientSession

# Configuration
MCP_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8090/sse")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "username")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")
USERSPACE = "smoke-test-userspace"


def _build_headers():
    creds = base64.b64encode(f"{ADMIN_USERNAME}:{ADMIN_PASSWORD}".encode()).decode()
    return {
        "Host": "localhost:8090",
        "Authorization": f"Basic {creds}",
    }


# --- Feed listing ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_feeds():
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("list_feeds", {"userspace": USERSPACE})
            text = res.content[0].text
            # Should return a parseable response (empty list or JSON)
            assert text is not None


# --- Search tools ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_articles():
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "search_articles", {"query": "test", "userspace": USERSPACE}
            )
            assert res.content[0].text is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_recent_articles():
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "get_recent_articles", {"userspace": USERSPACE, "hours": 1, "limit": 5}
            )
            assert res.content[0].text is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_events():
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "search_events", {"query": "test", "userspace": USERSPACE}
            )
            assert res.content[0].text is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_trends():
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "search_trends", {"query": "test", "userspace": USERSPACE}
            )
            assert res.content[0].text is not None


# --- User management ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_lifecycle():
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List users (should succeed even if empty)
            res = await session.call_tool("list_users", {})
            assert res.content[0].text is not None

            # Add user
            res = await session.call_tool(
                "add_user",
                {"email": "smoketest@example.com", "password": "testpass123", "role": "user"},
            )
            result_text = res.content[0].text
            assert result_text is not None

            # Try to parse user_id from response for cleanup
            try:
                result = json.loads(result_text)
                user_id = result.get("id") or result.get("user_id")
            except (json.JSONDecodeError, AttributeError):
                user_id = None

            if user_id:
                # Update role
                res = await session.call_tool(
                    "update_user_role", {"user_id": user_id, "role": "admin"}
                )
                assert res.content[0].text is not None

                # Delete user (cleanup)
                res = await session.call_tool("delete_user", {"user_id": user_id})
                assert res.content[0].text is not None


# --- Annotation tools ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_unannotated_articles():
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "list_unannotated_articles", {"userspace": USERSPACE, "limit": 5}
            )
            assert res.content[0].text is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_annotation_stats():
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "get_annotation_stats", {"userspace": USERSPACE}
            )
            assert res.content[0].text is not None


# --- Agent config tools ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_config_lifecycle():
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Add config
            res = await session.call_tool(
                "add_agent_config",
                {
                    "user_id": "smoke-test-user",
                    "name": "Smoke Test Agent",
                    "trigger_type": "schedule",
                    "target_db": "articles",
                    "logic_module": "test_module",
                    "schedule_interval": "60",
                },
            )
            result_text = res.content[0].text
            assert result_text is not None

            try:
                result = json.loads(result_text)
                agent_id = result.get("id") or result.get("agent_id")
            except (json.JSONDecodeError, AttributeError):
                agent_id = None

            # List configs
            res = await session.call_tool(
                "list_agent_configs", {"user_id": "smoke-test-user"}
            )
            assert res.content[0].text is not None

            if agent_id:
                # Get config
                res = await session.call_tool(
                    "get_agent_config", {"agent_id": agent_id}
                )
                assert res.content[0].text is not None

                # Update config
                res = await session.call_tool(
                    "update_agent_config",
                    {"agent_id": agent_id, "name": "Updated Smoke Test Agent"},
                )
                assert res.content[0].text is not None

                # Delete config (cleanup)
                res = await session.call_tool(
                    "delete_agent_config", {"agent_id": agent_id}
                )
                assert res.content[0].text is not None


# --- Staleness tools ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_staleness_tools():
    import re

    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Create a temporary event to mark as stale
            res = await session.call_tool(
                "add_event",
                {
                    "name": "Staleness Test Event",
                    "description": "Temporary event for staleness testing",
                    "article_links": [],
                    "userspace": USERSPACE,
                },
            )
            result_text = res.content[0].text
            match = re.search(r"Issue forged with ID: ([a-f0-9]+)", result_text)

            if match:
                event_id = match.group(1)

                # Mark as stale
                res = await session.call_tool(
                    "mark_entity_stale",
                    {"entity_type": "event", "entity_id": event_id, "is_stale": True},
                )
                assert res.content[0].text is not None

                # Unmark stale
                res = await session.call_tool(
                    "mark_entity_stale",
                    {"entity_type": "event", "entity_id": event_id, "is_stale": False},
                )
                assert res.content[0].text is not None

                # Cleanup
                await session.call_tool(
                    "delete_event", {"event_id": event_id, "userspace": USERSPACE}
                )
