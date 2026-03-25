# Moirai Developer Guide for AI Agents

This document provides essential instructions for AI agents working on the Moirai project. Adhere strictly to these guidelines to maintain code quality and system integrity.

---

## 0. Project Ethos: The Mythology of Moirai

Moirai is named after the Greek Fates — the three goddesses who weave the threads of destiny. This mythology provides a guiding philosophy for how we think about the system's architecture and the relationships between its components.

### The Metaphor

| Concept | Mythology | Moirai Equivalent |
|---------|-----------|-------------------|
| **Users (Admins)** | Olympians | Gods who rule, observe, and shape the world |
| **Users (Regular)** | Titans | Powerful beings, but scoped to their domain |
| **Userspaces** | Kingdoms / Realms | Sovereign territories where mortals dwell |
| **Agents** | Mortals / Heroes | Ephemeral workers who are born, act, and end |
| **Issues / Events / Trends** | Quests / Labors | Tasks that mortals pursue on behalf of the gods |
| **Articles** | Omens / Prophecies | Raw signals from the world, requiring interpretation |
| **Moirai (the system)** | The Fates | The loom that weaves all threads together |

### Guiding Principles

1. **Users are immortal; agents are mortal.**
   - Users persist across sessions. Their preferences, context, and identity endure.
   - Agents spin up, execute a mission, and terminate. They are ephemeral by design.
   - Do not store critical user data solely in agent memory — mortals fade, gods remain.

2. **Userspaces are sovereign kingdoms.**
   - Each userspace is an isolated realm. Agents (mortals) belong to one kingdom and cannot cross borders.
   - All data, issues, and events exist within a userspace. There is no "global" mortal realm.
   - Enforce isolation rigorously — a mortal from one kingdom must never see another's affairs.

3. **Agents serve the gods.**
   - Users summon agents to do their bidding. The relationship is asymmetric.
   - Agents should act autonomously but always in service of user intent.
   - When uncertain, agents should ask (or flag low confidence) rather than assume.

4. **Issues are quests with lifecycles.**
   - Issues are forged (created), measured (tracked), and sealed (completed/archived).
   - Like mortal quests, they have a beginning, middle, and end.
   - Some quests are heroic (major events); others are mundane (minor trends). Both matter.

5. **The Fates weave, but do not own.**
   - Moirai connects users, agents, and data — but the system should not hoard state.
   - Prefer explicit data flow over hidden caches. Prefer user-owned data over system-owned.
   - The loom reveals the pattern; it does not create it.

### How This Guides Development

When designing features or making architecture decisions, ask:

- **"Does this serve the gods (user value) or just the mortals (internal plumbing)?"**
- **"Is this agent acting like a hero (autonomous, resilient) or a servant (brittle, dependent)?"**
- **"Can a mortal from one kingdom see into another?"** (If yes, fix it.)
- **"Will this data outlive the agent that created it?"** (If it should, store it properly.)

This ethos is not about renaming code or enforcing mythology in APIs — it's a shared mental model for reasoning about the system's design and priorities.

---

## 1. Build, Run, and Test Commands

### Backend (Python/Flask/MCP)
- **Environment:** Conda (preferred) or venv. Python 3.10+.
- **Install Dependencies:**
  ```bash
  pip install -r requirements.txt
  # OR
  conda env update -f environment.yml
  ```
- **Run API Server:**
  ```bash
  python main.py
  ```
- **Run MCP Server:**
  ```bash
  python mcp_server.py
  ```
- **Run Tests (Pytest):**
  - **Run All Tests:**
    ```bash
    PYTHONPATH=. pytest
    ```
  - **Run Specific Test File:**
    ```bash
    PYTHONPATH=. pytest tests/test_mcp_crud.py
    ```
  - **Run Single Test Case:**
    ```bash
    PYTHONPATH=. pytest tests/test_mcp_crud.py::test_add_feed
    ```
  - **Run with Markers:**
    ```bash
    PYTHONPATH=. pytest -m "not integration"  # Skip slow integration tests
    ```

### Frontend (Vue.js 3 + TypeScript)
- **Directory:** `ui/`
- **Install Dependencies:**
  ```bash
  cd ui && yarn install
  ```
- **Run Dev Server:**
  ```bash
  cd ui && yarn dev
  ```
- **Build for Production:**
  ```bash
  cd ui && yarn build  # Runs vue-tsc type check then vite build
  ```
- **Run Tests (Playwright):**
  ```bash
  cd ui && yarnpkg playwright test
  ```

### Docker
- **Build and Run:**
  ```bash
  docker compose up --build
  ```
- **Local Build Metadata (non-GitHub builds):**
  ```bash
  BUILD_LABEL="CI $(date '+%Y-%m-%d %H:%M') build"

  docker build -f api/Dockerfile \
    --build-arg BUILD_NUMBER="$BUILD_LABEL" \
    -t rgsty.hlan.net/moirai:main .

  docker build -f ui/Dockerfile ui \
    --build-arg BUILD_NUMBER="$BUILD_LABEL" \
    -t rgsty.hlan.net/moirai-ui:main .
  ```
  This makes About show a custom build string instead of `build unknown`/empty for local images.

## 2. Code Style & Conventions

### Python (Backend)
- **Formatting:** Adhere to `black` (default settings).
- **Linting:** Adhere to `ruff` (default settings).
- **Type Hints:** REQUIRED for all function arguments and return values. Use `typing` module.
- **Imports:**
  - Group imports: Standard library, Third-party, Local application.
  - Absolute imports preferred (e.g., `from api.validation import ...`).
- **Docstrings:** Google-style docstrings for all functions and classes.
- **Error Handling:**
  - Use specific exceptions.
  - Wrap external calls (network, DB) in `try...except` blocks.
  - Log errors using `structlog` or standard `logging`.
- **Validation:** Use `pydantic` models for all API inputs.

### TypeScript/Vue (Frontend)
- **Formatting:** Adhere to `prettier` (config in `ui/package.json`).
  - Semi: `false`
  - Single Quote: `true`
  - Tab Width: `2`
- **Typing:** Strict typing with TypeScript. Avoid `any`.
- **Components:** Vue 3 Composition API (`<script setup lang="ts">`).
- **State Management:** Use `pinia` for global state (e.g., auth, filters).


## 3. Architecture & Critical Rules

### Security & Authentication
- **API Routes:** MUST use `@requires_auth` decorator in `api/routes.py`.
- **Sanitization:** All text inputs MUST be sanitized with `bleach.clean()`.
- **Validation:** Validate all inputs using `api/validation.py` Pydantic models.

### Data & Userspace Isolation
- **Userspace:** ALL MCP tools and API endpoints MUST require and validate a `userspace` UUID.
- **Isolation:** Ensure queries filter by `userspace` to prevent data leakage between agents/users.
- **Database:**
  - **CouchDB:** Use `get_doc`, `store_doc`, `update_doc` helpers.
  - **Conflict Handling:** ALWAYS fetch the latest `_rev` before updating a document.
  - **Pattern:**
    ```python
    existing = get_doc(db_name, doc_id)
    if existing:
        doc["_rev"] = existing["_rev"]
    ```
  - **Caching (Redis):**
    - Use `api.extensions.get_redis_client()` to get a configured client.
    - **Keys:** `stream_rss_xml`, `articles_default_json`.
    - **TTL:** 1 hour (3600s).
    - **Invalidation:** Cache is actively invalidated in `tasks.article_processor` (on ingestion) and `api.routes.delete_article`.

### Architecture Components
1.  **Flask REST API:** Serves UI and admin routes (`api/`).
2.  **MCP Server:** Provides tools for agents (`mcp_server.py`).
3.  **Vue UI:** Frontend dashboard (`ui/`).

### Common Tasks
- **Adding MCP Tool:**
  - Define in `mcp_server.py` with `@mcp.tool()`.
  - First argument MUST be `userspace: str`.
  - Validate `userspace` is a valid UUID.
- **Adding API Endpoint:**
  - Define in `api/routes.py`.
  - Use `@requires_auth`.
  - Validate input with Pydantic model.
  - Apply `bleach` sanitization to text inputs.
  - Return JSON responses with standard status codes.

### Release Process
- **Release and RC checklist:** Follow `docs/RELEASE.md` to avoid version/tag order issues.

### Troubleshooting
- **CouchDB:** Check if databases exist with `curl -u $COUCHDB_USER:$COUCHDB_PASSWORD http://localhost:5984/_all_dbs`.
- **Logs:** Check Docker logs with `docker compose logs -f moirai`.
- **Tests:** Use `-v` flag with pytest for verbose output.
