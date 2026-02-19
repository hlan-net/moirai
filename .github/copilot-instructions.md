# Moirai Development Guide

## Architecture Overview

Moirai is an MCP-powered press review platform with an agent-centric architecture. AI agents use MCP tools to aggregate RSS feeds, synthesize them into Events, and track Trends across isolated userspaces.

### Three-Tier Architecture

1. **Flask REST API** (port 8088)
   - Serves Vue.js UI and provides administrative CRUD operations
- Secured with HTTP Basic Auth (`ADMIN_USERNAME`/`ADMIN_PASSWORD`)
   - Routes: `api/routes.py` (admin), `api/chat_routes.py` (chat), `api/mcp_routes.py` (MCP proxy)

2. **MCP Server** (port 8090)
   - FastMCP SSE server providing agent tools (`mcp_server.py`)
   - Enforces userspace isolation (GUID required for all data operations)
   - Tools: `add_feed`, `list_feeds`, `read_feed`, `add_event`, `list_events`, `read_event`, `add_trend`, `list_trends`, `read_trend`

3. **Vue.js 3 + TypeScript UI** (in `ui/`)
   - 4-column layout: Feeds, Articles, Events, Trends
   - Cross-userspace review with userspace selector
   - Chat interface with built-in agent (uses MCP tools)

### Data Model

**CouchDB databases:** `feeds`, `articles`, `events`, `trends`

```
Userspace (GUID)
  └── Feeds (RSS sources)
       └── Articles (raw feed items)
            └── Events (groups of related articles)
                 └── Trends (patterns across events)
```

**Userspace Isolation:** All MCP tools require a `userspace` parameter (UUID/GUID). This ensures data segregation between different agent contexts.

## Build, Test, and Run

### Development Setup

```bash
# Full stack with Docker
docker compose up --build

# MCP server standalone (for debugging)
pip install -r requirements.txt
python mcp_server.py

# UI development server
cd ui
yarn install
yarn dev
```

### Testing

**Backend (Pytest):**
```bash
# Run all tests
PYTHONPATH=. ./venv/bin/pytest

# Run specific test file
PYTHONPATH=. ./venv/bin/pytest tests/test_live_lwn.py

# Run specific test
PYTHONPATH=. ./venv/bin/pytest tests/test_mcp_crud.py::test_add_feed
```

**Frontend (Playwright):**
```bash
cd ui

# First time: install browsers
npx playwright install

# Run all tests
yarnpkg playwright test

# Run specific test
yarnpkg playwright test tests/admin.spec.ts

# Run in headed mode for debugging
yarnpkg playwright test --headed
```

### Build Commands

**UI:**
```bash
cd ui
yarn build        # Production build → ui/dist/
vue-tsc -b        # Type check only
```

**Docker:**
```bash
docker compose up --build     # Rebuild and start
docker compose logs -f moirai # Watch logs
```

## Key Conventions

### Authentication & Security

- **API routes:** ALL routes in `api/routes.py` require `@requires_auth` decorator (HTTP Basic Auth)
- **Public read mode:** If `ALLOW_PUBLIC_READ=true`, GET endpoints skip auth
- **MCP userspace enforcement:** Every MCP tool validates `userspace` is a valid UUID
- **Input validation:** Use Pydantic models from `api/validation.py` for all request data
- **Sanitization:** All text inputs sanitized with `bleach.clean()` to prevent XSS

### CouchDB Interactions

**Conflict handling pattern:**
```python
# ALWAYS fetch latest _rev before updates
existing = get_doc(db_name, doc_id)
if existing:
    doc["_rev"] = existing["_rev"]  # Prevent 409 conflicts
```

**Common DB helpers in `mcp_server.py`:**
- `get_doc(db_name, doc_id)` → dict or None
- `store_doc(db_name, doc)` → doc_id (auto-generates hash ID if missing)
- `update_doc(db_name, doc_id, updates)` → updated doc
- `delete_doc(db_name, doc_id)` → success bool

### Userspace Filtering

**Backend pattern (in API routes):**
```python
userspace = request.args.get('userspace')
if userspace:
    validate_userspace_param(userspace)
    # Filter query: ?include_docs=true
    # Then filter results: [d for d in docs if d.get('userspace') == userspace]
```

**MCP tool pattern:**
```python
@mcp.tool()
def some_tool(userspace: str, other_params: str):
    """All tools MUST require userspace parameter first"""
    if not userspace:
        raise ValueError("userspace is required")
    # Validate UUID format
    try:
        uuid.UUID(userspace)
    except ValueError:
        raise ValueError("Invalid userspace GUID format")
    # ... rest of logic
```

### RSS Feed Processing

**Feed fetching (in `tasks/article_processor.py`):**
- Always uses `feedparser` to parse RSS/Atom feeds
- Handles multiple date formats: `published_parsed`, `updated_parsed`
- Generates hash IDs for deduplication: `hashlib.sha256(link.encode()).hexdigest()[:16]`
- Respects `ARTICLE_EXPIRATION_DAYS` env var (default: 30)

**Feed URL validation:**
- Must be http/https only (no file://, javascript:, etc.)
- Validated by `validators.url()` and Pydantic `HttpUrl`

### Frontend Conventions

**Component structure:**
- `ui/src/components/` - Reusable components
- `ui/src/views/` - Route-level views (AdminView.vue, ChatView.vue, SettingsView.vue)
- `ui/src/router/` - Vue Router config

**State management:**
- No Vuex/Pinia - uses `localStorage` for chat history and settings
- Userspace selected via dropdown persisted in `sessionStorage`

**API calls:**
- Use native `fetch()` with Basic Auth headers
- Pattern: `headers: { 'Authorization': 'Basic ' + btoa(username + ':' + password) }`

### Environment Variables

**Required:**
- `COUCHDB_URI` - CouchDB connection string
- `COUCHDB_USER` / `COUCHDB_PASSWORD` - DB credentials
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` - HTTP Basic Auth for API

**Optional:**
- `ALLOW_PUBLIC_READ` (default: false) - Allow unauthenticated GET requests
- `ARTICLE_EXPIRATION_DAYS` (default: 30) - Auto-cleanup threshold
- `ITERATION_INTERVAL` (default: 300) - Legacy scheduler interval (mostly unused)
- `MODEL_NAME` (default: llama3.1:latest) - LLM model for chat
- `OLLAMA_BASE_URL` (default: http://host.docker.internal:11434/v1) - LLM endpoint

### File Organization

**Do NOT modify:**
- `tasks/scheduler.py` - Legacy scheduler (decommissioned but kept for reference)
- `security_enhancements.md` - Planning document (not active code)

**Core logic locations:**
- Feed parsing: `tasks/article_processor.py`
- Database init: `tasks/init.py`
- MCP tools: `mcp_server.py` (tool definitions start around line 100)
- API routes: `api/routes.py` (admin), `api/chat_routes.py` (chat proxy)
- Validation: `api/validation.py` (Pydantic models)

## Common Tasks

### Adding a New MCP Tool

1. Add tool function in `mcp_server.py`:
```python
@mcp.tool()
def my_new_tool(userspace: str, param: str) -> str:
    """Tool description for agent"""
    # Validate userspace
    try:
        uuid.UUID(userspace)
    except ValueError:
        raise ValueError("Invalid userspace")
    # ... implementation
    return result
```

2. No registration needed - FastMCP auto-discovers `@mcp.tool()` decorated functions
3. Test via MCP client or built-in chat interface

### Adding a New API Endpoint

1. Define validation model in `api/validation.py`:
```python
class MyRequest(BaseModel):
    field: str = Field(..., max_length=100)
    @validator('field')
    def sanitize(cls, v):
        return bleach.clean(v, tags=[], strip=True)
```

2. Add route in `api/routes.py`:
```python
@api_blueprint.route('/my-endpoint', methods=['POST'])
@requires_auth  # ALWAYS include this
@limiter.limit("20 per minute")
def my_endpoint():
    try:
        data = MyRequest(**request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    # ... implementation
```

### Debugging CouchDB Issues

```bash
# Check if databases exist
curl -u username:password http://localhost:5984/_all_dbs

# View all docs in a database
curl -u username:password http://localhost:5984/feeds/_all_docs?include_docs=true

# Check specific document
curl -u username:password http://localhost:5984/feeds/{doc_id}

# Create system databases if missing
curl -X PUT -u username:password http://localhost:5984/_users
curl -X PUT -u username:password http://localhost:5984/_replicator
```

### Testing the Chat Interface

1. Ensure Ollama is running: `ollama serve`
2. Pull a model with tool support: `ollama pull llama3.1`
3. Access chat at: `http://localhost:8088/chat`
4. Go to Settings if you need to change model or endpoint

## Architecture Evolution Notes

This project transitioned from an autonomous scheduled service to agent-centric MCP architecture:

- **Old approach:** `scheduler.py` ran periodic jobs to fetch feeds automatically
- **New approach:** Agents call MCP tools on-demand (`read_feed`, `add_event`, etc.)
- **Legacy code:** `tasks/scheduler.py` still exists but is not used in production

The rewrite prioritized:
1. Userspace isolation for multi-tenant security
2. HTTP Basic Auth for API access
3. Pydantic validation for input sanitization
4. Agent-friendly MCP tool interface
5. Human oversight via admin UI
