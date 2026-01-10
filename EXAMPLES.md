# Moirai Usage & Testing Examples

This guide provides practical examples for interacting with Moirai's API and MCP services.

## 1. Manual API Testing (Administrative)

The Flask API (port 8088) requires **HTTP Basic Auth**.

### List Feeds
```bash
curl -u <YOUR_USERNAME>:<YOUR_PASSWORD> http://localhost:8088/api/feeds
```

### Delete an Article
```bash
curl -X DELETE -u <YOUR_USERNAME>:<YOUR_PASSWORD> http://localhost:8088/api/articles/<ARTICLE_ID>
```

### Remove a Link from an Event
```bash
curl -X DELETE -u <YOUR_USERNAME>:<YOUR_PASSWORD> \
     -H "Content-Type: application/json" \
     -d '{"link": "https://example.com/noisy-article"}' \
     http://localhost:8088/api/events/<EVENT_ID>/links
```

---

## 2. MCP Server Interaction (Agent-style)

The MCP server (port 8090) uses **SSE** transport. While agents call these tools automatically, you can test them using any MCP client (like `mcp-cli`) or by writing a simple script.

### Example Tool Calls
If you are using an LLM agent, it will "see" these tools. Here is how they are structured:

**Add a Feed to a Namespace:**
```json
// Tool: add_feed
{
  "url": "https://lwn.net/headlines/rss",
  "namespace": "550e8400-e29b-41d4-a716-446655440000",
  "category": "linux"
}
```

**Synthesize an Event:**
```json
// Tool: add_event
{
  "name": "Linux Kernel 6.13 Release",
  "description": "A summary of the latest kernel features based on these articles.",
  "article_links": ["https://lwn.net/articles/123", "https://wired.com/kernel-news"],
  "namespace": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 3. Automated Testing Suite

### Backend Tests (Pytest)
Ensure your virtual environment is active and dependencies are installed.
```bash
# Run all unit and integration tests
PYTHONPATH=. ./venv/bin/pytest

# Run specific live integration test for LWN
PYTHONPATH=. ./venv/bin/pytest tests/test_live_lwn.py
```

### UI Tests (Playwright)
The UI tests verify the frontend loads and the columns are visible.
```bash
cd ui
# Install browsers if running for the first time
npx playwright install 

# Run the tests
yarnpkg playwright test
```

---

## 4. Troubleshooting

### CouchDB System Databases
If CouchDB logs errors about `_users` not existing on a fresh install:
```bash
curl -X PUT http://<YOUR_USERNAME>:<YOUR_PASSWORD>@localhost:5984/_users
curl -X PUT http://<YOUR_USERNAME>:<YOUR_PASSWORD>@localhost:5984/_replicator
curl -X PUT http://<YOUR_USERNAME>:<YOUR_PASSWORD>@localhost:5984/_global_changes
```

### Docker Logs
Monitor the ingestion pipeline in real-time:
```bash
docker compose logs -f moirai
```
