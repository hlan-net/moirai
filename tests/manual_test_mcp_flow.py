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
                feeds_list = await session.call_tool(
                    "list_feeds", {"userspace": "test-userspace"}
                )
                print(f"Initial Feeds: {feeds_list.content[0].text[:50]}...")

                add_feed_result = await session.call_tool(
                    "add_feed",
                    {
                        "url": "https://example.com/test-feed.xml",
                        "title": "Test Feed",
                        "userspace": "test-userspace",
                        "category": "test",
                    },
                )
                print(f"Add Feed Result: {add_feed_result.content[0].text}")

                # 2. Test Events (Userspace / Transient Issues)
                print("\n--- Testing Events (Userspace / Transient Issues) ---")
                auto_userspace = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                event_auto = await session.call_tool(
                    "add_event",
                    {
                        "name": "Auto Event",
                        "description": "Event with generated userspace",
                        "article_links": ["http://example.com/1"],
                        "userspace": auto_userspace,
                    },
                )
                print(f"Add Event (Auto) Result: {event_auto.content[0].text}")

                # Extract GUID from response "Issue forged with ID: ... in userspace: <GUID>"
                output_text = event_auto.content[0].text
                import re

                auto_userspace = None
                match = re.search(r"userspace: ([a-f0-9\-]+)", output_text)
                if match:
                    auto_userspace = match.group(1)
                    print(f"Captured Userspace: {auto_userspace}")

                    # Verify we can list it using that userspace
                    list_res = await session.call_tool(
                        "list_issues", {"userspace": auto_userspace, "longevity": "transient"}
                    )
                    print(f"List Events (Auto NS): {list_res.content[0].text}")
                else:
                    print("FAILED to capture auto userspace.")

                # 3. Test Events (Client Userspace / Transient Issues)
                print("\n--- Testing Events (Client Userspace / Transient Issues) ---")
                client_userspace = "11111111-2222-3333-4444-555555555555"
                event_client = await session.call_tool(
                    "add_event",
                    {
                        "name": "Client Event",
                        "description": "Event with client userspace",
                        "article_links": ["http://example.com/2"],
                        "userspace": client_userspace,
                    },
                )
                print(f"Add Event (Client) Result: {event_client.content[0].text}")

                # Verify listing
                list_client = await session.call_tool(
                    "list_issues", {"userspace": client_userspace, "longevity": "transient"}
                )
                print(f"List Events (Client NS): {list_client.content[0].text}")

                # 4. Isolation Check
                print("\n--- Testing Isolation ---")
                # Check auto userspace for client event (should NOT be there)
                if auto_userspace:
                    list_iso = await session.call_tool(
                        "list_issues", {"userspace": auto_userspace, "longevity": "transient"}
                    )
                    if "Client Event" not in list_iso.content[0].text:
                        print("SUCCESS: Client Event not found in Auto Userspace.")
                    else:
                        print("FAILURE: Isolation breach.")

    except Exception as e:
        print(f"Test Failed: {e}")
        # Print detailed traceback if possible
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mcp_flow())
