import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client


async def test_mcp_flow():
    url = "http://localhost:8090/sse"
    print(f"Connecting to MCP server at {url}...")

    try:
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Connected to MCP Server!")

                # 1. Test Feeds (Global)
                print("\n--- Testing Feeds (Global) ---")
                feeds_list = await session.call_tool("list_feeds", {{}})
                print(f"Initial Feeds: {feeds_list.content[0].text[:50]}...")

                add_feed_result = await session.call_tool(
                    "add_feed",
                    {"url": "https://example.com/test-feed.xml", "category": "test"},
                )
                print(f"Add Feed Result: {add_feed_result.content[0].text}")

                # 2. Test Events (Auto Namespace)
                print("\n--- Testing Events (Auto Namespace) ---")
                event_auto = await session.call_tool(
                    "add_event",
                    {
                        "name": "Auto Event",
                        "description": "Event with auto-generated namespace",
                        "article_links": ["http://example.com/1"],
                    },
                )
                print(f"Add Event (Auto) Result: {event_auto.content[0].text}")

                # Extract GUID from response "Event created with ID: ... in namespace: <GUID>"
                output_text = event_auto.content[0].text
                import re

                match = re.search(r"namespace: ([a-f0-9\-]+)", output_text)
                if match:
                    auto_namespace = match.group(1)
                    print(f"Captured Namespace: {auto_namespace}")

                    # Verify we can list it using that namespace
                    list_res = await session.call_tool(
                        "list_events", {{"namespace": auto_namespace}}
                    )
                    print(f"List Events (Auto NS): {list_res.content[0].text}")
                else:
                    print("FAILED to capture auto namespace.")

                # 3. Test Events (Client Namespace)
                print("\n--- Testing Events (Client Namespace) ---")
                client_ns = "11111111-2222-3333-4444-555555555555"
                event_client = await session.call_tool(
                    "add_event",
                    {
                        "name": "Client Event",
                        "description": "Event with client namespace",
                        "article_links": ["http://example.com/2"],
                        "namespace": client_ns,
                    },
                )
                print(f"Add Event (Client) Result: {event_client.content[0].text}")

                # Verify listing
                list_client = await session.call_tool(
                    "list_events", {{"namespace": client_ns}}
                )
                print(f"List Events (Client NS): {list_client.content[0].text}")

                # 4. Isolation Check
                print("\n--- Testing Isolation ---")
                # Check auto namespace for client event (should NOT be there)
                if match:
                    list_iso = await session.call_tool(
                        "list_events", {{"namespace": auto_namespace}}
                    )
                    if "Client Event" not in list_iso.content[0].text:
                        print("SUCCESS: Client Event not found in Auto Namespace.")
                    else:
                        print("FAILURE: Isolation breach.")

    except Exception as e:
        print(f"Test Failed: {e}")
        # Print detailed traceback if possible
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mcp_flow())
