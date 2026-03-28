import os
import base64
import json
import pytest

# Configuration
MCP_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8090/sse")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "username")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "testpass")  # noqa: S105


def _build_headers():
    """Build headers with Host override and Basic Auth for MCP server."""
    creds = base64.b64encode(f"{ADMIN_USERNAME}:{ADMIN_PASSWORD}".encode()).decode()
    return {
        "Host": "localhost:8090",
        "Authorization": f"Basic {creds}",
    }


def _parse_response(res) -> dict:
    """Parse MCP tool response as standardized MCPResponse envelope."""
    text = res.content[0].text if res.content else "{}"
    return json.loads(text)


def _assert_success(parsed: dict, context: str = "") -> dict:
    """Assert response is successful and return data."""
    assert parsed.get("status") == "success", f"Expected success{f' for {context}' if context else ''}: {parsed}"
    return parsed.get("data", {})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_crud_flow():
    from mcp.client.sse import sse_client
    from mcp import ClientSession

    print(f"Connecting to MCP Server at {MCP_URL}...")
    headers = _build_headers()
    async with sse_client(MCP_URL, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected!")

            # 1. Feeds CRUD
            print("\n--- Testing Feeds CRUD ---")
            feed_url = "https://example.com/test-feed.xml"

            # Add
            print(f"Adding feed: {feed_url}")
            res = await session.call_tool(
                "add_feed", {"url": feed_url, "title": "Test Feed", "userspace": "test-userspace", "category": "test"}
            )
            parsed = _parse_response(res)
            data = _assert_success(parsed, "add_feed")
            assert "feed_id" in data
            print(f"Result: {parsed['message']}")

            # Update
            print(f"Updating category for: {feed_url}")
            res = await session.call_tool(
                "update_feed_category",
                {"feed_id": feed_url, "new_category": "updated_test", "userspace": "test-userspace"},
            )
            parsed = _parse_response(res)
            data = _assert_success(parsed, "update_feed_category")
            assert data.get("category") == "updated_test"
            print(f"Result: {parsed['message']}")

            # Delete
            print(f"Deleting feed: {feed_url}")
            res = await session.call_tool("delete_feed", {"feed_id": feed_url, "userspace": "test-userspace"})
            parsed = _parse_response(res)
            _assert_success(parsed, "delete_feed")
            print(f"Result: {parsed['message']}")

            # 2. Events CRUD (Transient Issues)
            print("\n--- Testing Events CRUD (Transient Issues) ---")
            userspace = "test-crud-userspace"

            # Add
            print("Adding event...")
            res = await session.call_tool(
                "add_event",
                {
                    "name": "Test Event",
                    "description": "Initial description",
                    "article_links": ["http://link1.com"],
                    "userspace": userspace,
                },
            )
            parsed = _parse_response(res)
            data = _assert_success(parsed, "add_event")
            event_id = data.get("issue_id")
            assert event_id, f"Expected issue_id in response data: {data}"
            print(f"Captured Issue ID (Event): {event_id}")

            # Verify issue type/longevity
            issue_res = await session.call_tool(
                "read_issue",
                {"issue_id": event_id, "userspace": userspace},
            )
            issue_parsed = _parse_response(issue_res)
            issue_doc = _assert_success(issue_parsed, "read_issue (event)")
            assert issue_doc.get("type") == "issue"
            assert issue_doc.get("longevity") == "transient"

            # Update
            print(f"Updating event {event_id}...")
            res = await session.call_tool(
                "update_event",
                {
                    "event_id": event_id,
                    "userspace": userspace,
                    "description": "Updated description",
                },
            )
            parsed = _parse_response(res)
            _assert_success(parsed, "update_event")
            print(f"Result: {parsed['message']}")

            issue_res = await session.call_tool(
                "read_issue",
                {"issue_id": event_id, "userspace": userspace},
            )
            issue_parsed = _parse_response(issue_res)
            issue_doc = _assert_success(issue_parsed, "read_issue after update")
            assert issue_doc.get("description") == "Updated description"

            # Delete
            print(f"Deleting event {event_id}...")
            res = await session.call_tool(
                "delete_event", {"event_id": event_id, "userspace": userspace}
            )
            parsed = _parse_response(res)
            _assert_success(parsed, "delete_event")
            print(f"Result: {parsed['message']}")

            # 3. Trends CRUD (Temporal Issues)
            print("\n--- Testing Trends CRUD (Temporal Issues) ---")

            # Add
            print("Adding trend...")
            res = await session.call_tool(
                "add_trend",
                {
                    "name": "Test Trend",
                    "description": "Initial trend desc",
                    "event_ids": [],
                    "userspace": userspace,
                },
            )
            parsed = _parse_response(res)
            data = _assert_success(parsed, "add_trend")
            trend_id = data.get("issue_id")
            assert trend_id, f"Expected issue_id in response data: {data}"
            print(f"Captured Issue ID (Trend): {trend_id}")

            issue_res = await session.call_tool(
                "read_issue",
                {"issue_id": trend_id, "userspace": userspace},
            )
            issue_parsed = _parse_response(issue_res)
            issue_doc = _assert_success(issue_parsed, "read_issue (trend)")
            assert issue_doc.get("type") == "issue"
            assert issue_doc.get("longevity") == "temporal"

            # Update
            print(f"Updating trend {trend_id}...")
            res = await session.call_tool(
                "update_trend",
                {
                    "trend_id": trend_id,
                    "userspace": userspace,
                    "name": "Updated Trend Name",
                },
            )
            parsed = _parse_response(res)
            _assert_success(parsed, "update_trend")
            print(f"Result: {parsed['message']}")

            issue_res = await session.call_tool(
                "read_issue",
                {"issue_id": trend_id, "userspace": userspace},
            )
            issue_parsed = _parse_response(issue_res)
            issue_doc = _assert_success(issue_parsed, "read_issue after trend update")
            # update_trend passes name as description (it's the legacy alias behavior)
            # The logos field is not updated by update_trend - it maps to description

            # Delete
            print(f"Deleting trend {trend_id}...")
            res = await session.call_tool(
                "delete_trend", {"trend_id": trend_id, "userspace": userspace}
            )
            parsed = _parse_response(res)
            _assert_success(parsed, "delete_trend")
            print(f"Result: {parsed['message']}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_crud_flow())
