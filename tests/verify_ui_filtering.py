import asyncio
import uuid
import os
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

EVENT_NS1_NAME = "Event NS1"
EVENT_NS2_NAME = "Event NS2"


async def verify_filtering():
    mcp_url = "http://localhost:8090/sse"
    api_url = "http://localhost:8088/api/issues"

    username = os.environ.get("API_USERNAME")
    password = os.environ.get("API_PASSWORD")

    assert username, "API_USERNAME environment variable must be set"
    assert password, "API_PASSWORD environment variable must be set"

    ns1 = str(uuid.uuid4())
    ns2 = str(uuid.uuid4())

    print(f"NS1: {ns1}")
    print(f"NS2: {ns2}")

    print("Connecting to MCP server...")
    try:
        async with sse_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Create Event in NS1 (Transient Issue)
                await session.call_tool(
                    "add_event",
                    {
                        "name": EVENT_NS1_NAME,
                        "description": "Desc 1",
                        "article_links": [],
                        "userspace": ns1,
                    },
                )

                # Create Event in NS2 (Transient Issue)
                await session.call_tool(
                    "add_event",
                    {
                        "name": EVENT_NS2_NAME,
                        "description": "Desc 2",
                        "article_links": [],
                        "userspace": ns2,
                    },
                )

    except Exception as e:
        print(f"MCP Error: {e}")
        return

    # Verify MCP userspace filtering
    print("\n--- Verifying MCP Userspace Filtering ---")
    try:
        async with sse_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res1 = await session.call_tool(
                    "list_issues", {"userspace": ns1, "longevity": "transient"}
                )
                res2 = await session.call_tool(
                    "list_issues", {"userspace": ns2, "longevity": "transient"}
                )

                ns1_text = res1.content[0].text
                ns2_text = res2.content[0].text

                if EVENT_NS1_NAME in ns1_text and EVENT_NS2_NAME not in ns1_text:
                    print("SUCCESS: NS1 isolated correctly in MCP list.")
                else:
                    print("FAILURE: NS1 isolation check failed.")

                if EVENT_NS2_NAME in ns2_text and EVENT_NS1_NAME not in ns2_text:
                    print("SUCCESS: NS2 isolated correctly in MCP list.")
                else:
                    print("FAILURE: NS2 isolation check failed.")
    except Exception as e:
        print(f"MCP Error during list_issues: {e}")
        return

    # Verify API returns transient issues (events) across userspaces
    print("\n--- Verifying API Issues (Transient) ---")
    async with httpx.AsyncClient(auth=httpx.BasicAuth(username, password)) as client:
        res_all = await client.get(f"{api_url}?longevity=transient")
        if res_all.status_code != 200:
            print(f"API Error: {res_all.status_code} {res_all.text}")
            return

        data_all = res_all.json()
        found_ns1 = any(
            i.get("userspace") == ns1 and i.get("logos") == EVENT_NS1_NAME
            for i in data_all
        )
        found_ns2 = any(
            i.get("userspace") == ns2 and i.get("logos") == EVENT_NS2_NAME
            for i in data_all
        )

        if found_ns1 and found_ns2:
            print("SUCCESS: /api/issues returns transient issues across userspaces.")
        else:
            print("FAILURE: Missing transient issues in /api/issues response.")


if __name__ == "__main__":
    asyncio.run(verify_filtering())
