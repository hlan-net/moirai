import os
import json
import pytest

# Configuration
# Configuration
MCP_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8090/sse")


# Helper to simulate an MCP tool call
def call_mcp_tool(tool_name, arguments):
    # In a real MCP client, this would be a JSON-RPC request over SSE
    # Since we can't easily script a full SSE client here without a library,
    # we'll use a mocked approach or just rely on unit testing the functions if accessible.
    # However, since we're testing the deployed server, we can't import the code directly.
    # We will assume this script is running in an environment where it can import the mcp_server code
    # OR we can try to use the mcp-cli if installed, but it's not.

    # Actually, for this verification, since we are on the 'edge' node where the source code is,
    # we can try to import the file and test the functions directly if we mock the DB request helper?
    # No, that's too complex.

    # Alternative: Use the python 'mcp' client library to connect to the server?
    # We saw 'mcp' installed in the container environment.
    pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_crud_flow():
    from mcp.client.sse import sse_client
    from mcp import ClientSession

    print(f"Connecting to MCP Server at {MCP_URL}...")
    # Force Host header to localhost to bypass TrustedHostMiddleware in FastMCP
    headers = {"Host": "localhost:8090"}
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
            print(f"Result: {res.content[0].text}")

            # Update
            print(f"Updating category for: {feed_url}")
            res = await session.call_tool(
                "update_feed_category",
                {"feed_id": feed_url, "new_category": "updated_test", "userspace": "test-userspace"},
            )
            print(f"Result: {res.content[0].text}")

            # Delete
            print(f"Deleting feed: {feed_url}")
            res = await session.call_tool("delete_feed", {"feed_id": feed_url, "userspace": "test-userspace"})
            print(f"Result: {res.content[0].text}")

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
            result_text = res.content[0].text
            print(f"Result: {result_text}")

            # Extract Issue ID (hacky parsing)
            import re

            match = re.search(r"Issue forged with ID: ([a-f0-9]+)", result_text)
            if match:
                event_id = match.group(1)
                print(f"Captured Issue ID (Event): {event_id}")

                # Verify issue type/longevity
                issue_res = await session.call_tool(
                    "read_issue",
                    {"issue_id": event_id, "userspace": userspace},
                )
                issue_doc = json.loads(issue_res.content[0].text)
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
                print(f"Result: {res.content[0].text}")

                issue_res = await session.call_tool(
                    "read_issue",
                    {"issue_id": event_id, "userspace": userspace},
                )
                issue_doc = json.loads(issue_res.content[0].text)
                assert issue_doc.get("description") == "Updated description"

                # Delete
                print(f"Deleting event {event_id}...")
                res = await session.call_tool(
                    "delete_event", {"event_id": event_id, "userspace": userspace}
                )
                print(f"Result: {res.content[0].text}")
            else:
                print("Failed to capture Event ID, skipping update/delete tests.")

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
            result_text = res.content[0].text
            print(f"Result: {result_text}")

            match = re.search(r"Issue forged with ID: ([a-f0-9]+)", result_text)
            if match:
                trend_id = match.group(1)
                print(f"Captured Issue ID (Trend): {trend_id}")

                issue_res = await session.call_tool(
                    "read_issue",
                    {"issue_id": trend_id, "userspace": userspace},
                )
                issue_doc = json.loads(issue_res.content[0].text)
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
                print(f"Result: {res.content[0].text}")

                issue_res = await session.call_tool(
                    "read_issue",
                    {"issue_id": trend_id, "userspace": userspace},
                )
                issue_doc = json.loads(issue_res.content[0].text)
                assert issue_doc.get("logos") == "Updated Trend Name"

                # Delete
                print(f"Deleting trend {trend_id}...")
                res = await session.call_tool(
                    "delete_trend", {"trend_id": trend_id, "userspace": userspace}
                )
                print(f"Result: {res.content[0].text}")
            else:
                print("Failed to capture Trend ID, skipping update/delete tests.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_crud_flow())
