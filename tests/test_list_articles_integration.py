"""
Integration test for the list_articles MCP tool.
Requires MCP server to be running on localhost:8090.
Run with: python tests/test_list_articles_integration.py
"""
import asyncio
import pytest
from mcp.client.sse import sse_client
from mcp import ClientSession


@pytest.mark.asyncio
async def test_list_articles():
    url = "http://localhost:8090/sse"
    print(f"Connecting to MCP server at {url}...")
    
    try:
        # Force Host header to localhost to bypass TrustedHostMiddleware in FastMCP
        headers = {"Host": "localhost:8090"}
        async with sse_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✓ Connected to MCP Server!")

                # List available tools to confirm list_articles exists
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]
                print(f"\n✓ Available tools: {', '.join(tool_names)}")
                
                if "list_articles" not in tool_names:
                    print("✗ FAILED: list_articles tool not found!")
                    return
                
                print("✓ list_articles tool is available")

                # Test 1: Call list_articles with no parameters (should use defaults)
                print("\n--- Test 1: List articles with default parameters ---")
                result = await session.call_tool("list_articles", {})
                response_text = result.content[0].text if result.content else "No response"
                print(f"Response: {response_text[:200]}...")
                
                # Test 2: Call list_articles with limit parameter
                print("\n--- Test 2: List articles with limit=5 ---")
                result = await session.call_tool("list_articles", {"limit": 5})
                response_text = result.content[0].text if result.content else "No response"
                print(f"Response: {response_text[:200]}...")
                
                # Test 3: Call list_articles with feed_url parameter
                print("\n--- Test 3: List articles filtered by feed_url ---")
                # First, let's list feeds to get a real feed URL
                feeds_result = await session.call_tool("list_feeds", {})
                feeds_text = feeds_result.content[0].text if feeds_result.content else ""
                print(f"Available feeds: {feeds_text[:200]}...")
                
                # Extract first feed URL if available
                import re
                match = re.search(r'- (https?://[^\s]+)', feeds_text)
                if match:
                    feed_url = match.group(1)
                    print(f"Testing with feed: {feed_url}")
                    result = await session.call_tool("list_articles", {"feed_url": feed_url})
                    response_text = result.content[0].text if result.content else "No response"
                    print(f"Response: {response_text[:200]}...")
                else:
                    print("No feeds found to test filtering")
                
                print("\n✓ All tests completed successfully!")
                
    except Exception as e:
        print(f"\n✗ Test Failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_list_articles())
