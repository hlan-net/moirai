# Fix Summary: Agent Article Fetching Issue

## Problem
When users asked the agent to "check recent articles", the agent would return an error without any details. The issue occurred because the agent did not have a tool to list articles from the database.

### Original Behavior
- User: "Check the recent articles"
- Agent: "Error: " (no details)
- Agent then listed available feeds instead of actually showing articles

## Root Cause
The MCP server had tools to:
- `list_feeds` - List RSS feed sources
- `read_feed` - Fetch articles directly from an RSS feed URL

But there was **no tool to list articles already stored in the database**. When the agent tried to show recent articles without specifying a feed URL, it had no way to do so.

## Solution
Added a new MCP tool: `list_articles`

### Tool Specification
```python
@mcp.tool()
def list_articles(limit: int = 20, feed_url: str = None) -> str:
    """
    List recent articles from the database.
    
    If feed_url is provided, returns articles only from that specific feed.
    Otherwise, returns recent articles from all feeds.
    
    Args:
        limit: Maximum number of articles to return (default: 20, max: 100)
        feed_url: Optional feed URL to filter articles
    """
```

### Features
1. **Lists articles from database** - Shows articles already fetched and stored
2. **Sorting** - Returns newest articles first (by published date)
3. **Filtering** - Can filter by specific feed URL
4. **Limit control** - Configurable result count (1-100 articles)
5. **Helpful error messages** - When no articles are found, suggests using `read_feed`
6. **HTML sanitization** - Removes HTML tags from summaries for clean display

### Output Format
```
Title: Example Article
Link: https://example.com/article
Published: 2024-02-04T10:00:00
Feed: https://example.com/feed
Summary: Article summary text...

---

Title: Another Article
...
```

## Changes Made

### 1. MCP Server (`mcp_server.py`)
- Added `list_articles` tool with full error handling
- Tool supports optional `limit` and `feed_url` parameters
- Implements sorting, filtering, and HTML cleaning

### 2. Chat Routes (`api/chat_routes.py`)
- Updated system prompt to inform agent about `list_articles` tool
- Added guidance: "When asked for recent articles or news, use `list_articles`"

### 3. Tests (`tests/test_list_articles_tool.py`)
- Unit tests for formatting logic
- Test for empty database handling
- Test for feed URL filtering

### 4. Integration Test (`tests/test_list_articles_integration.py`)
- End-to-end test for the MCP tool
- Verifies tool registration and availability
- Tests multiple parameter combinations

### 5. Documentation (`EXAMPLES.md`)
- Added examples of using `list_articles` tool
- Documented both basic and filtered usage

## Testing

### Unit Tests
```bash
python -m pytest tests/test_list_articles_tool.py -v
```
All tests pass ✓

### Integration Test (requires running services)
```bash
python tests/test_list_articles_integration.py
```

### Manual Test
1. Start services: `docker compose up --build`
2. Access chat: http://localhost:8088/chat
3. Ask: "What are the recent articles?"
4. Agent should now call `list_articles` tool and display results

## Expected Agent Behavior After Fix

### User: "Check the recent articles"
**Agent will now:**
1. Call `list_articles` tool (with default limit of 20)
2. Display formatted list of recent articles from the database
3. If database is empty, suggest using `read_feed` to fetch from RSS feeds

### User: "Show me articles from BBC News"
**Agent will:**
1. Call `list_feeds` to find BBC feed URL
2. Call `list_articles` with `feed_url` parameter
3. Display filtered results

## Error Handling Improvements
- Returns helpful message when database is empty
- Suggests alternative action (`read_feed`) when no articles found
- Validates and clamps limit parameter (1-100 range)
- Skips CouchDB design documents
- Handles missing fields gracefully with defaults

## Backward Compatibility
- All existing tools continue to work
- No breaking changes to API or MCP server
- New tool is additive - doesn't modify existing behavior
