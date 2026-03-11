# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Moirai is a GenAI-native press review platform built on the Model Context Protocol (MCP). AI agents use MCP tools to aggregate RSS feeds, synthesize articles into Events, and track Trends — all within isolated userspaces (UUID-scoped). A Vue.js dashboard lets humans review the agent's work.

## Architecture

Three main services:

- **Flask REST API** (`main.py`, `api/`) — port 8088, serves UI and admin CRUD. Uses gunicorn in production, with worker/scheduler started separately via `run_worker.py`.
- **MCP Server** (`mcp_server.py` → `mcp_service/`) — Starlette/FastMCP SSE server on port 8090. Tool modules live in `mcp_service/tools/` (feeds, issues, search, staleness, users, agent_configs, annotations). Includes Redis cache, AgentOrchestrator background thread, and a dedicated Prometheus metrics server on port 9000.
- **Vue.js 3 UI** (`ui/`) — Vite + TypeScript + Pinia. 4-column admin layout (Feeds, Articles, Events, Trends) with chat interface.

**Data storage:** CouchDB (databases: `feeds`, `articles`, `issues`/events/trends). Redis for caching (TTL 3600s, invalidated on ingestion/deletion).

**Data model:** Userspace (UUID) → Feeds → Articles → Events → Trends. All MCP tools and API queries must filter by userspace.

## Build & Run Commands

### Full stack (Docker)
```bash
docker compose up --build
```

### Local Docker build metadata (non-GitHub builds)
Set `BUILD_NUMBER` when building local images so About displays a meaningful build label instead of `build unknown`/empty.

```bash
BUILD_LABEL="CI $(date '+%Y-%m-%d %H:%M') build"

docker build -f api/Dockerfile \
  --build-arg BUILD_NUMBER="$BUILD_LABEL" \
  -t rgsty.hlan.net/moirai:main .

docker build -f ui/Dockerfile ui \
  --build-arg BUILD_NUMBER="$BUILD_LABEL" \
  -t rgsty.hlan.net/moirai-ui:main .
```

### Backend (local dev)
```bash
mamba env create -f environment.yml   # or: pip install -r requirements.txt
mamba activate moirai
python main.py                        # API on :8088
python mcp_server.py                  # MCP on :8090
```

### Frontend
```bash
cd ui
yarn install
yarn dev          # Dev server
yarn build        # Type-check (vue-tsc) + production build
```

### Testing

**Python (pytest):**
```bash
pytest                                          # Unit tests only (integration skipped by default)
pytest tests/test_mcp_crud.py                   # Specific file
pytest tests/test_mcp_crud.py::test_add_feed    # Specific test
pytest -m integration                           # Integration tests only
```
`pytest.ini` sets `pythonpath = .` and `addopts = -v -m "not integration"`.

**Frontend (Playwright):**
```bash
cd ui
npx playwright install          # First time only
npx playwright test             # All tests
npx playwright test tests/admin.spec.ts   # Specific test
```

### Linting & Formatting
Pre-commit hooks run `black`, `ruff`, `trailing-whitespace`, `end-of-file-fixer`. Frontend uses `prettier` via `lint-staged` (husky).
```bash
ruff check . --fix              # Python lint
black .                         # Python format
cd ui && npx prettier --write . # Frontend format
```

### CI
GitHub Actions (`ci.yml`): two jobs — `test` (conda env + ruff + pytest + Docker build) and `ui-test` (yarn + Playwright against docker-compose stack).

## Key Conventions

### Security & Auth
- API routes MUST use `@requires_auth` decorator (`api/auth.py`). Public read mode available via `ALLOW_PUBLIC_READ=true`.
- MCP tools: first parameter MUST be `userspace: str`, validated as UUID.
- All text inputs sanitized with `bleach.clean()`. Request validation via Pydantic models in `api/validation.py`.
- CSRF enabled by default (Flask-WTF); disabled in test mode or via `DISABLE_CSRF=true`.

### CouchDB Pattern
Always fetch latest `_rev` before updates to avoid 409 conflicts:
```python
existing = get_doc(db_name, doc_id)
if existing:
    doc["_rev"] = existing["_rev"]
```

### Python Style
- Formatting: `black` (defaults). Linting: `ruff`.
- Type hints required on function signatures.
- Imports: stdlib → third-party → local, absolute preferred.
- Logging: `structlog` or standard `logging`.

### Frontend Style
- Vue 3 Composition API (`<script setup lang="ts">`), strict TypeScript.
- Prettier config: no semicolons, single quotes, 2-space indent, 100 print width.
- CSS variables for theming (dark mode default) — see `ui/STYLE_GUIDE.md`.
- Always use `<style scoped>`.
- State: Pinia stores in `ui/src/stores/`.

### Adding an MCP Tool
Define in `mcp_service/tools/` with `@mcp.tool()`. First arg must be `userspace: str` with UUID validation. FastMCP auto-discovers decorated functions — no registration needed.

### Adding an API Endpoint
1. Pydantic model in `api/validation.py` with `bleach.clean()` sanitization.
2. Route in `api/routes.py` with `@requires_auth` and `@limiter.limit()`.

## Environment Variables

Required: `COUCHDB_URI`, `COUCHDB_USER`, `COUCHDB_PASSWORD`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `JWT_SECRET_KEY`, `REDIS_PASSWORD`.

Notable optional: `ALLOW_PUBLIC_READ`, `ARTICLE_EXPIRATION_DAYS` (default 30), `MODEL_NAME`, `DEFAULT_LLM_PROVIDER` (ollama/openai/gemini), `METRICS_PORT` (default 9000), `DISABLE_CSRF`, `DISABLE_RATE_LIMIT`.
