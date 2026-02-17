import asyncio
import uuid
import re
from mcp import ClientSession
from mcp.client.sse import sse_client


async def verify_trends():
    url = "http://localhost:8090/sse"
    print(f"Connecting to MCP server at {url}...")

    try:
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("Connected to MCP Server!")

                # Generate a test namespace
                namespace = str(uuid.uuid4())
                print(f"Using Test Namespace: {namespace}")

                # 1. Create a dummy event (transient issue) needed for a trend
                print("\n--- Creating Test Event (Transient Issue) ---")
                event_res = await session.call_tool(
                    "add_event",
                    {
                        "name": "Trend Test Event",
                        "description": "An event to test trend creation",
                        "article_links": ["http://example.com/trend-test"],
                        "namespace": namespace,
                    },
                )
                print(f"Add Event Result: {event_res.content[0].text}")

                # Extract Issue ID (Event)
                match = re.search(
                    r"Issue forged with ID: ([a-f0-9]+)", event_res.content[0].text
                )
                if not match:
                    print("Failed to get Event ID. Cannot proceed to create trend.")
                    return

                event_id = match.group(1)
                print(f"Captured Event ID: {event_id}")

                # 2. Create a Trend
                print("\n--- Creating Test Trend ---")
                trend_name = "Emerging Test Trend"
                trend_res = await session.call_tool(
                    "add_trend",
                    {
                        "name": trend_name,
                        "description": "A trend created by the verification script",
                        "event_ids": [event_id],
                        "namespace": namespace,
                    },
                )
                print(f"Add Trend Result: {trend_res.content[0].text}")

                # 3. List Issues (Temporal) and Verify
                print("\n--- Verifying Trend Existence (Temporal Issue) ---")
                list_res = await session.call_tool(
                    "list_issues", {"namespace": namespace, "longevity": "temporal"}
                )
                output = list_res.content[0].text
                print(f"List Trends Output:\n{output}")

                if trend_name in output:
                    print("\nSUCCESS: Trend found in the list!")
                else:
                    print("\nFAILURE: Trend NOT found in the list.")

    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(verify_trends())
