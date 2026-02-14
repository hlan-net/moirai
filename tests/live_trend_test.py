import asyncio
import uuid
import re
from mcp import ClientSession
from mcp.client.sse import sse_client


async def live_trend_test():
    url = "http://localhost:8090/sse"
    print(f"Connecting to MCP server at {url}...")

    try:
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Connected to MCP Server!")

                # Use a specific namespace for this live test
                namespace = str(uuid.uuid4())
                print(f"Using Live Test Namespace: {namespace}")

                # 1. Add/Ensure Feed
                feed_url = "https://feeds.bbci.co.uk/news/rss.xml"
                print(f"\n--- Adding Feed: {feed_url} ---")
                await session.call_tool(
                    "add_feed", {"url": feed_url, "category": "news"}
                )

                # 2. Read Feed
                print("\n--- Reading Feed ---")
                read_res = await session.call_tool(
                    "read_feed", {"url": feed_url, "limit": 3}
                )
                articles_text = read_res.content[0].text
                print(f"Fetched Articles (first 200 chars):\n{articles_text[:200]}...")

                # Parse out links (simplistic regex)
                links = re.findall(r"Link: (https?://[^\s]+)", articles_text)
                if not links:
                    print("No links found in feed. Cannot proceed.")
                    return

                print(f"Found {len(links)} article links.")

                # 3. Create Event from first 2 links
                print("\n--- Creating Event from Real Articles ---")
                event_name = "BBC Top Stories"
                event_res = await session.call_tool(
                    "add_event",
                    {
                        "name": event_name,
                        "description": "Top stories fetched from BBC RSS",
                        "article_links": links[:2],
                        "namespace": namespace,
                    },
                )
                print(f"Add Event Result: {event_res.content[0].text}")

                # Extract Event ID
                match = re.search(
                    r"Event created with ID: ([a-f0-9]+)", event_res.content[0].text
                )
                if not match:
                    print("Failed to get Event ID.")
                    return
                event_id = match.group(1)

                # 4. Create Trend
                print("\n--- Creating Trend from Event ---")
                trend_name = "Global News Snapshot"
                trend_res = await session.call_tool(
                    "add_trend",
                    {
                        "name": trend_name,
                        "description": "A snapshot trend from live BBC data",
                        "event_ids": [event_id],
                        "namespace": namespace,
                    },
                )
                print(f"Add Trend Result: {trend_res.content[0].text}")

                # 5. Verify
                print("\n--- Verifying Trend ---")
                list_res = await session.call_tool(
                    "list_trends", {"namespace": namespace}
                )
                output = list_res.content[0].text
                print(f"List Trends Output:\n{output}")

                if trend_name in output:
                    print("\nSUCCESS: Real-data Trend created and verified!")
                else:
                    print("\nFAILURE: Trend not found.")

    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(live_trend_test())
