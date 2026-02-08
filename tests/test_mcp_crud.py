import requests
import json
import os
import time
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
    async with sse_client(MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected!")

            # 1. Feeds CRUD
            print("\n--- Testing Feeds CRUD ---")
            feed_url = "https://example.com/test-feed.xml"
            
            # Add
            print(f"Adding feed: {feed_url}")
            res = await session.call_tool("add_feed", {"url": feed_url, "category": "test"})
            print(f"Result: {res.content[0].text}")

            # Update
            print(f"Updating category for: {feed_url}")
            res = await session.call_tool("update_feed_category", {"url": feed_url, "new_category": "updated_test"})
            print(f"Result: {res.content[0].text}")

            # Delete
            print(f"Deleting feed: {feed_url}")
            res = await session.call_tool("delete_feed", {"url": feed_url})
            print(f"Result: {res.content[0].text}")

            # 2. Events CRUD
            print("\n--- Testing Events CRUD ---")
            namespace = "test-crud-namespace"
            
            # Add
            print("Adding event...")
            res = await session.call_tool("add_event", {
                "name": "Test Event", 
                "description": "Initial description", 
                "article_links": ["http://link1.com"], 
                "namespace": namespace
            })
            result_text = res.content[0].text
            print(f"Result: {result_text}")
            
            # Extract Event ID (hacky parsing)
            import re
            match = re.search(r"ID: ([a-f0-9]+)", result_text)
            if match:
                event_id = match.group(1)
                print(f"Captured Event ID: {event_id}")

                # Update
                print(f"Updating event {event_id}...")
                res = await session.call_tool("update_event", {
                    "event_id": event_id, 
                    "namespace": namespace,
                    "description": "Updated description"
                })
                print(f"Result: {res.content[0].text}")

                # Delete
                print(f"Deleting event {event_id}...")
                res = await session.call_tool("delete_event", {
                    "event_id": event_id, 
                    "namespace": namespace
                })
                print(f"Result: {res.content[0].text}")
            else:
                print("Failed to capture Event ID, skipping update/delete tests.")

            # 3. Trends CRUD
            print("\n--- Testing Trends CRUD ---")
            
            # Add
            print("Adding trend...")
            res = await session.call_tool("add_trend", {
                "name": "Test Trend", 
                "description": "Initial trend desc", 
                "event_ids": [], 
                "namespace": namespace
            })
            result_text = res.content[0].text
            print(f"Result: {result_text}")
            
            match = re.search(r"ID: ([a-f0-9]+)", result_text)
            if match:
                trend_id = match.group(1)
                print(f"Captured Trend ID: {trend_id}")

                # Update
                print(f"Updating trend {trend_id}...")
                res = await session.call_tool("update_trend", {
                    "trend_id": trend_id, 
                    "namespace": namespace,
                    "name": "Updated Trend Name"
                })
                print(f"Result: {res.content[0].text}")

                # Delete
                print(f"Deleting trend {trend_id}...")
                res = await session.call_tool("delete_trend", {
                    "trend_id": trend_id, 
                    "namespace": namespace
                })
                print(f"Result: {res.content[0].text}")
            else:
                print("Failed to capture Trend ID, skipping update/delete tests.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_crud_flow())
