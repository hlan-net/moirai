import asyncio
import uuid
import requests
import os
from mcp import ClientSession
from mcp.client.sse import sse_client


async def verify_filtering():
    mcp_url = "http://localhost:8090/sse"
    api_url = "http://localhost:8088/api/events"

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

                # Create Event in NS1
                await session.call_tool(
                    "add_event",
                    {
                        "name": "Event NS1",
                        "description": "Desc 1",
                        "article_links": [],
                        "namespace": ns1,
                    },
                )

                # Create Event in NS2
                await session.call_tool(
                    "add_event",
                    {
                        "name": "Event NS2",
                        "description": "Desc 2",
                        "article_links": [],
                        "namespace": ns2,
                    },
                )

    except Exception as e:
        print(f"MCP Error: {e}")
        return

    # Verify API Filtering
    print("\n--- Verifying API Filtering ---")

    # 1. Fetch NS1
    res1 = requests.get(f"{api_url}?namespace={ns1}", auth=(username, password))
    if res1.status_code != 200:
        print(f"API Error: {res1.status_code} {res1.text}")
        return

    data1 = res1.json()
    print(f"NS1 Events Count: {len(data1)}")
    if len(data1) == 1 and data1[0]["namespace"] == ns1:
        print("SUCCESS: NS1 filtered correctly.")
    else:
        print(f"FAILURE: Expected 1 event for NS1, got {len(data1)}: {data1}")

    # 2. Fetch NS2
    res2 = requests.get(f"{api_url}?namespace={ns2}", auth=(username, password))
    data2 = res2.json()
    print(f"NS2 Events Count: {len(data2)}")
    if len(data2) == 1 and data2[0]["namespace"] == ns2:
        print("SUCCESS: NS2 filtered correctly.")
    else:
        print(f"FAILURE: Expected 1 event for NS2, got {len(data2)}")

    # 3. Fetch All (or at least check it returns multiple)
    # Note: Fetching all might be large, but we check if it contains both
    res_all = requests.get(api_url, auth=(username, password))
    data_all = res_all.json()

    found_ns1 = any(e.get("namespace") == ns1 for e in data_all)
    found_ns2 = any(e.get("namespace") == ns2 for e in data_all)

    if found_ns1 and found_ns2:
        print("SUCCESS: No filter returns both.")
    else:
        print("FAILURE: Missing events in default view.")


if __name__ == "__main__":
    asyncio.run(verify_filtering())
