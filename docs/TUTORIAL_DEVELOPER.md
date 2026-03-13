# Moirai Developer Guide: Building & Contributing

Welcome, developer! This guide covers setting up a local development environment, understanding the architecture, and extending Moirai with custom features.

---

## Part 1: Development Environment Setup

### Prerequisites
- **Python 3.10+** (check: `python --version`)
- **Node.js 18+** (check: `node --version`)
- **Git** (check: `git --version`)
- **Docker** (recommended, check: `docker --version`)
- **Mamba or Conda** (for Python environment isolation)

### Step 1: Clone & Navigate
```bash
git clone https://github.com/your-org/moirai.git
cd moirai
```

### Step 2: Set Up Python Environment
```bash
# Using mamba (faster than conda)
mamba env create -f environment.yml
mamba activate moirai

# Or using conda
conda env create -f environment.yml
conda activate moirai

# Or using pip
pip install -r requirements.txt
```

### Step 3: Start External Services (Docker recommended)
```bash
# Start CouchDB, Redis, Ollama in background
docker compose up -d couchdb redis

# Verify they're running
docker compose ps
```

### Step 4: Set Environment Variables
```bash
# Create .env.local
cat > .env.local <<EOF
COUCHDB_URI=http://localhost:5984/
COUCHDB_USER=admin
COUCHDB_PASSWORD=password
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
REDIS_PASSWORD=redis_password
DEFAULT_LLM_PROVIDER=ollama
MODEL_NAME=llama2
OLLAMA_BASE_URL=http://localhost:11434
DISABLE_CSRF=true
DISABLE_RATE_LIMIT=true
EOF

# Load variables
source .env.local
```

### Step 5: Initialize Databases
```bash
python -c "from api.db import init_dbs; init_dbs()"
```

### Step 6: Start Development Servers (3 Terminal Windows)

**Terminal 1: Flask API**
```bash
python main.py
# Starts on http://localhost:8088
# Auto-reloads on file changes
```

**Terminal 2: MCP Server**
```bash
python mcp_server.py
# Starts on http://localhost:8090
# Includes AgentOrchestrator & AnnotationWorker daemons
```

**Terminal 3: Worker & Scheduler**
```bash
python run_worker.py
# Background jobs
```

**Terminal 4: Frontend (separate, from ui/ directory)**
```bash
cd ui
yarn install  # First time only
yarn dev
# Starts on http://localhost:5173
# Hot-reloads on file changes
```

### Step 7: Verify Setup
```bash
# Check API health
curl http://localhost:8088/api/health

# Check MCP Server
curl http://localhost:8090/health

# Access UI
open http://localhost:5173
# Login: admin / password (from .env.local)
```

---

## Part 2: Project Structure

```
moirai/
├── api/                          # Flask REST API
│   ├── main.py                   # Entry point
│   ├── routes.py                 # API endpoints
│   ├── auth.py                   # Authentication & JWT
│   ├── validation.py             # Pydantic models, security allowlists
│   ├── db.py                     # CouchDB helpers
│   ├── db_config.py              # Database configuration
│   └── llm.py                    # LLM provider abstractions
│
├── mcp_service/                  # MCP Server (Starlette)
│   ├── core.py                   # FastMCP setup
│   ├── mcp_server.py             # Entry point
│   └── tools/                    # MCP tool definitions
│       ├── feeds.py              # Feed management tools
│       ├── issues.py             # Issue/Event tools
│       ├── articles.py           # Article tools
│       ├── search.py             # Search tools
│       ├── agent_configs.py      # Agent configuration tools
│       ├── annotations.py        # Annotation tools
│       └── user_management.py    # User tools
│
├── tasks/                        # Background workers & agents
│   ├── agent_orchestrator.py     # Main agent dispatcher (distributed lock)
│   ├── annotation_worker.py      # LLM article annotation (changes feed)
│   ├── agent_logic.py            # Agent logic functions
│   ├── agent_config_migration.py # Legacy config migration
│   └── annotator.py              # LLM annotation service
│
├── ui/                           # Vue.js 3 frontend
│   ├── src/
│   │   ├── main.ts               # Entry point
│   │   ├── App.vue               # Root component
│   │   ├── components/           # Reusable components
│   │   │   ├── AdminDashboard.vue
│   │   │   ├── ArticleList.vue
│   │   │   ├── EventList.vue
│   │   │   ├── TrendList.vue
│   │   │   ├── ChatInterface.vue
│   │   │   └── ContextChatModal.vue
│   │   ├── stores/               # Pinia state management
│   │   │   ├── articles.ts
│   │   │   ├── issues.ts
│   │   │   ├── chat.ts
│   │   │   └── auth.ts
│   │   ├── views/                # Page components
│   │   │   ├── AdminView.vue
│   │   │   ├── ChatPage.vue
│   │   │   ├── LifespanView.vue
│   │   │   └── RiverView.vue
│   │   └── styles/               # Global CSS
│   │       └── variables.css
│   └── package.json
│
├── tests/                        # Test suite
│   ├── test_agent_orchestrator.py
│   ├── test_agent_routes.py
│   ├── test_auth_flow.py
│   ├── test_mcp_crud.py
│   └── ... (30+ test files)
│
├── docs/                         # Documentation
│   ├── TUTORIAL_USER.md
│   ├── TUTORIAL_ADMIN.md
│   ├── TUTORIAL_DEVELOPER.md     # You are here
│   └── STYLE_GUIDE.md
│
├── CLAUDE.md                     # Instructions for Claude Code
├── CHANGELOG.md                  # Version history
├── docker-compose.yml            # Local development stack
├── environment.yml               # Conda/Mamba dependencies
└── requirements.txt              # Pip dependencies

```

---

## Part 3: Architecture Deep Dive

### Data Model

```
Userspace (UUID-scoped)
  └─ Feeds (RSS feeds)
      └─ Articles (ingested feed items)
          └─ Annotations (AI-generated metadata)
          └─ Issues/Events (AI-grouped articles)
              └─ Trends (patterns across events)
```

Every document in CouchDB includes `userspace` for isolation.

### Request Flow: Article → Event → Trend

1. **Ingestion** → Feed scheduler fetches new articles
2. **Annotation** → `AnnotationWorker` longpolls `articles/_changes`, adds `annotations` field
3. **Grouping** → `AgentOrchestrator` (ON_NEW_ARTICLE trigger) calls `create_event_from_articles` agent logic
4. **Trends** → `AgentOrchestrator` (SCHEDULED trigger) calls trend detection agent logic
5. **UI Display** → React queries `/api/articles`, `/api/issues`, `/api/trends`
6. **Chat** → User asks questions via `/api/chat` endpoint

### Component Interaction

```
┌────────────────────────────────────────────────────────────┐
│                    Vue.js UI (3000)                        │
│  (AdminDashboard, ArticleList, Chat, etc.)                │
└────────────────────────────────────────────────────────────┘
                              ↕ HTTP/JSON
┌────────────────────────────────────────────────────────────┐
│              Flask REST API (8088)                         │
│  /api/articles, /api/issues, /api/chat, etc.             │
└────────────────────────────────────────────────────────────┘
                              ↕
┌────────────────────────────────────────────────────────────┐
│                  CouchDB (5984)                            │
│  feeds, articles, issues, agent_configs, annotations      │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│              MCP Server (8090)                             │
│  AgentOrchestrator (agent dispatch)                       │
│  AnnotationWorker (article annotation)                    │
│  Tools (feeds, issues, articles, etc.)                    │
└────────────────────────────────────────────────────────────┘
                              ↕
┌────────────────────────────────────────────────────────────┐
│                    Redis (6379)                            │
│  Caching, distributed locks, session store               │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                   LLM (ollama/openai)                      │
│  Article annotation, event synthesis, trend detection     │
└────────────────────────────────────────────────────────────┘
```

---

## Part 4: Common Development Tasks

### Task 1: Add a New API Endpoint

**Goal:** Create `/api/custom-endpoint` that returns custom data.

#### 1. Define Request/Response Models
```python
# api/validation.py
from pydantic import BaseModel

class CustomRequest(BaseModel):
    filter_term: str

class CustomResponse(BaseModel):
    count: int
    items: list[str]
```

#### 2. Add Route
```python
# api/routes.py
from flask import request
from api.auth import requires_auth
from api.validation import CustomRequest, CustomResponse

@app.route("/api/custom-endpoint", methods=["POST"])
@requires_auth
def custom_endpoint():
    try:
        req = CustomRequest(**request.json)
        userspace = request.headers.get("X-Userspace")

        # Query CouchDB with userspace isolation
        results = query_couchdb(
            "articles",
            selector={
                "userspace": userspace,
                "title": {"$regex": req.filter_term}
            }
        )

        response = CustomResponse(
            count=len(results),
            items=[r["title"] for r in results]
        )
        return response.model_dump(), 200
    except Exception as e:
        logger.error(f"Error in custom_endpoint: {e}")
        return {"error": str(e)}, 500
```

#### 3. Test It
```bash
curl -X POST http://localhost:8088/api/custom-endpoint \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filter_term": "AI"}'
```

### Task 2: Add a New MCP Tool

**Goal:** Create a tool that counts articles by topic.

#### 1. Define Tool
```python
# mcp_service/tools/custom_tools.py
from mcp_service.core import mcp
from api.db import query_couchdb

@mcp.tool()
def count_articles_by_topic(userspace: str, topic: str) -> dict:
    """Count articles matching a topic in the given userspace."""
    if not is_valid_uuid(userspace):
        raise ValueError(f"Invalid userspace: {userspace}")

    articles = query_couchdb(
        "articles",
        selector={
            "userspace": userspace,
            "annotations.topics": {"$elemMatch": {"$regex": topic}}
        }
    )

    return {
        "topic": topic,
        "count": len(articles),
        "articles": [a["_id"] for a in articles[:10]]
    }
```

#### 2. Register Tool (Auto-discovered)
MCP tools are auto-discovered by FastMCP. No registration needed!

#### 3. Test It
```bash
# The tool is now available in agent logic:
def my_agent_logic(agent_config, mcp_client, **kwargs):
    result = mcp_client.call_tool(
        "count_articles_by_topic",
        userspace=agent_config["userspace"],
        topic="AI"
    )
    print(f"Found {result['count']} articles about AI")
```

### Task 3: Add Custom Agent Logic

**Goal:** Create an agent that tags articles by priority.

#### 1. Implement Logic Function
```python
# tasks/agent_logic.py
import logging
logger = logging.getLogger(__name__)

def tag_articles_by_priority(
    agent_config: dict,
    mcp_client,
    new_articles: list[dict] = None,
    llm_config: dict = None,
) -> None:
    """
    Analyze articles and tag them as HIGH/MEDIUM/LOW priority.
    Runs on new articles (ON_NEW_ARTICLE trigger).
    """
    if not new_articles:
        return

    userspace = agent_config.get("userspace")
    from api.llm import get_llm_provider

    llm = get_llm_provider(llm_config)

    for article in new_articles:
        title = article.get("title", "")
        summary = article.get("summary", "")

        # Call LLM to analyze
        prompt = f"""Rate this article priority (HIGH/MEDIUM/LOW):
Title: {title}
Summary: {summary}
Response format: {{priority: "HIGH"}}
"""
        response = llm.generate(prompt)
        priority = response.get("priority", "MEDIUM")

        # Store result
        article["priority_tag"] = priority
        mcp_client.call_tool(
            "update_article",
            userspace=userspace,
            article_id=article["_id"],
            updates={"priority_tag": priority}
        )

        logger.info(f"Tagged article {article['_id']} as {priority}")
```

#### 2. Add to Allowlist
```python
# api/validation.py
ALLOWED_LOGIC_MODULES = {
    "tasks.agent_logic.create_event_from_articles",
    "tasks.agent_logic.tag_articles_by_priority",  # NEW
    ...
}
```

#### 3. Create Agent Config (via CouchDB admin or API)
```json
{
  "_id": "priority-tagger",
  "name": "Article Priority Tagger",
  "userspace": "default-workspace-uuid",
  "trigger_type": "ON_NEW_ARTICLE",
  "logic_module": "tasks.agent_logic.tag_articles_by_priority",
  "status": "ACTIVE",
  "llm_model_config": {
    "provider": "openai",
    "model": "gpt-4"
  }
}
```

### Task 4: Write Tests

**Goal:** Test the priority tagging agent.

#### 1. Unit Test
```python
# tests/test_agent_logic_custom.py
import pytest
from unittest.mock import MagicMock, patch
from tasks.agent_logic import tag_articles_by_priority

@patch('tasks.agent_logic.get_llm_provider')
def test_tag_articles_by_priority(mock_get_llm):
    mock_llm = MagicMock()
    mock_llm.generate.return_value = {"priority": "HIGH"}
    mock_get_llm.return_value = mock_llm

    agent_config = {
        "userspace": "test-uuid",
        "logic_module": "tasks.agent_logic.tag_articles_by_priority"
    }

    new_articles = [
        {
            "_id": "art1",
            "title": "Breaking: New AI Breakthrough",
            "summary": "Researchers announce..."
        }
    ]

    mcp_client = MagicMock()

    tag_articles_by_priority(
        agent_config=agent_config,
        mcp_client=mcp_client,
        new_articles=new_articles,
        llm_config=None
    )

    # Verify it called update_article
    mcp_client.call_tool.assert_called()
    call_args = mcp_client.call_tool.call_args
    assert call_args[0][0] == "update_article"
    assert call_args[1]["updates"]["priority_tag"] == "HIGH"
```

#### 2. Run Tests
```bash
# Run specific test
pytest tests/test_agent_logic_custom.py::test_tag_articles_by_priority -v

# Run all tests
pytest

# Run with coverage
pytest --cov=tasks --cov=api
```

---

## Part 5: Key Patterns & Guidelines

### Pattern 1: Userspace Isolation

**Every query must filter by userspace:**

```python
# ✅ CORRECT
articles = query_couchdb(
    "articles",
    selector={
        "userspace": userspace,  # REQUIRED
        "title": {"$regex": search_term}
    }
)

# ❌ WRONG - would leak data across users
articles = query_couchdb(
    "articles",
    selector={
        "title": {"$regex": search_term}  # Missing userspace!
    }
)
```

### Pattern 2: Conflict-Safe CouchDB Updates

```python
# ✅ CORRECT - uses conflict-safe helper
update_couchdb_doc_safe(
    "articles",
    article_id,
    {"priority_tag": "HIGH"}
)

# ⚠️ OK but riskier - manual _rev handling
existing = query_couchdb("articles", selector={"_id": article_id})
if existing:
    existing[0]["priority_tag"] = "HIGH"
    existing[0]["_rev"] = existing[0]["_rev"]  # Fetch latest _rev
    # Update...
```

### Pattern 3: Changes Feed (Event-Driven)

**For listening to new documents:**

```python
# ✅ CORRECT - longpoll changes feed with sequence tracking
def _run_changes_feed(self):
    self.last_seq = self._get_last_seq()
    while self.running:
        response = requests.get(
            f"{get_couchdb_uri()}articles/_changes",
            params={
                "feed": "longpoll",
                "since": self.last_seq,
                "include_docs": "true",
                "timeout": 30000
            },
            timeout=35
        )
        if response.status_code == 200:
            data = response.json()
            self.last_seq = data["last_seq"]
            self._save_last_seq(self.last_seq)  # Persist for restarts

# ❌ WRONG - polling without event-driven approach
while True:
    articles = query_couchdb(
        "articles",
        selector={"published": {"$gt": last_check_time}}
    )
    # Process...
    time.sleep(60)  # Inefficient, up to 60s latency
```

### Pattern 4: Error Handling in Agents

```python
# ✅ CORRECT - catch & log errors without crashing
def my_agent_logic(agent_config, mcp_client, **kwargs):
    try:
        # Do work...
        mcp_client.call_tool(...)
    except ValueError as e:
        logger.warning(f"Invalid input: {e}")
        # Continue processing next item
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        # Agent orchestrator will mark agent as ERROR
        raise

# ❌ WRONG - silently swallow errors
def my_agent_logic(agent_config, mcp_client, **kwargs):
    try:
        mcp_client.call_tool(...)
    except:
        pass  # Don't hide errors!
```

---

## Part 6: Testing Guide

### Running Tests

```bash
# All unit tests (integration skipped by default)
pytest

# Specific test file
pytest tests/test_agent_orchestrator.py -v

# Specific test
pytest tests/test_agent_orchestrator.py::test_check_and_run_agents_scheduled -v

# Integration tests (requires external services)
pytest -m integration

# With coverage report
pytest --cov=api --cov=tasks --cov-report=html
# Open htmlcov/index.html
```

### Test Structure

```python
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_redis():
    return MagicMock()

def test_something(mock_redis):
    # Arrange
    config = {...}

    # Act
    result = my_function(config, mock_redis)

    # Assert
    assert result == expected
    mock_redis.method.assert_called_once_with(...)
```

### Mock Common Objects

```python
# Mock CouchDB queries
@patch('api.db.query_couchdb')
def test_with_mock_db(mock_query):
    mock_query.return_value = [{"_id": "doc1", "title": "..."}]
    # Now any query_couchdb() call returns this

# Mock MCP client
mcp_client = MagicMock()
mcp_client.call_tool.return_value = {"result": "value"}

# Mock LLM
@patch('api.llm.get_llm_provider')
def test_with_llm(mock_llm_provider):
    mock_llm = MagicMock()
    mock_llm.generate.return_value = {"text": "response"}
    mock_llm_provider.return_value = mock_llm
```

---

## Part 7: Code Style & Conventions

### Python Style

```python
# Type hints on all functions
def create_issue(userspace: str, title: str, articles: list[dict]) -> dict:
    pass

# Imports: stdlib → third-party → local
import json
from datetime import datetime
import requests
from pydantic import BaseModel
from api.db import query_couchdb
from api.validation import AgentStatus

# Use docstrings
def important_function(x: int) -> str:
    """
    Brief one-liner.

    Longer description if needed.

    Args:
        x: Input value

    Returns:
        String result
    """
    pass

# Logging
import logging
logger = logging.getLogger(__name__)
logger.info("Starting process")
logger.error(f"Failed: {e}", exc_info=True)
```

### Frontend (Vue/TypeScript)

```typescript
// Strict TypeScript
<script setup lang="ts">
import { ref, computed } from 'vue'

interface Article {
  id: string
  title: string
  published: string
}

const articles = ref<Article[]>([])

// Use Pinia for state
import { useArticleStore } from '@/stores/articles'
const store = useArticleStore()
store.fetchArticles()
</script>

<style scoped>
/* No semicolons, prefer CSS variables */
.article {
  color: var(--text-primary);
  padding: var(--spacing-md);
}
</style>
```

---

## Part 8: Debugging Tips

### Backend Debugging

```python
# Add logging
logger.debug(f"Articles found: {results}")

# Use pdb for interactive debugging
import pdb; pdb.set_trace()
# Then: n (next), s (step), c (continue), l (list)

# Check logs
docker compose logs -f api
docker compose logs -f mcp_server

# Query CouchDB directly
curl http://localhost:5984/articles/_all_docs?include_docs=true
```

### Frontend Debugging

```javascript
// Browser DevTools (F12)
// Network tab → Check API calls
// Console tab → Check errors
// Vue DevTools → Inspect state

// Add console logs
console.log('Articles:', articles.value)
console.error('Error:', error)

// Vite HMR debug
// Check browser console for HMR errors
```

### Database Debugging

```bash
# Access CouchDB admin UI
open http://localhost:5984/_utils

# Query with curl
curl -H "Content-Type: application/json" \
  -d '{"selector": {"userspace": "test-uuid"}}' \
  http://localhost:5984/articles/_find

# Check Redis
docker compose exec redis redis-cli
> KEYS *
> GET key-name
```

---

## Part 9: Contributing Guidelines

### Before You Start
1. Check [GitHub Issues](https://github.com/your-org/moirai/issues) for related work
2. Comment on the issue to claim it
3. Create a feature branch: `git checkout -b feat/my-feature`

### During Development
1. **Write tests** as you code (TDD encouraged)
2. **Run tests locally:** `pytest`
3. **Check formatting:** `black . && ruff check .`
4. **Update CLAUDE.md** if you change architecture

### Before Submitting PR
1. **All tests pass:** `pytest`
2. **Linting clean:** `black . && ruff check . --fix`
3. **Frontend tests pass:** `cd ui && npm run test`
4. **Commit message clear:** `feat(agent): add priority tagging logic`

### PR Checklist
- [ ] Tests added/updated
- [ ] Linting passes
- [ ] Documentation updated (if needed)
- [ ] Userspace isolation verified (if dealing with data)
- [ ] No hardcoded credentials or secrets
- [ ] Backward compatible (or migration included)

---

## Part 10: Useful Resources

| Topic | Link |
|-------|------|
| **CouchDB Docs** | https://docs.couchdb.org |
| **FastMCP** | https://github.com/anthropics/python-sdk (MCP section) |
| **Vue 3** | https://vuejs.org/guide |
| **Flask** | https://flask.palletsprojects.com |
| **Redis** | https://redis.io/commands |
| **Pytest** | https://docs.pytest.org |
| **GitHub Issues** | See moirai repository |

---

## Quick Reference

| Task | Command |
|------|---------|
| Start dev | `python main.py` (in 3 terminals) |
| Run tests | `pytest` |
| Run linter | `black . && ruff check .` |
| Add to allowlist | Edit `api/validation.py` |
| Check logs | `docker compose logs -f api` |
| Database admin | Open `http://localhost:5984/_utils` |
| Access UI | Open `http://localhost:5173` |
| Git branch | `git checkout -b feat/name` |
| Commit | `git commit -m "feat(module): description"` |

---

**Happy coding!** 🚀 If you hit issues, check the repo's GitHub Issues or ask on Discussions.
