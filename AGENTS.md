# Moirai Developer Guide for AI Agents

This document provides essential instructions for AI agents working on the Moirai project. Adhere strictly to these guidelines to maintain code quality and system integrity.

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

### Data & Namespace Isolation
- **Namespace:** ALL MCP tools and API endpoints MUST require and validate a `namespace` UUID.
- **Isolation:** Ensure queries filter by `namespace` to prevent data leakage between agents/users.
- **Database:**
  - **CouchDB:** Use `get_doc`, `store_doc`, `update_doc` helpers.
  - **Conflict Handling:** ALWAYS fetch the latest `_rev` before updating a document.
  - **Pattern:**
    ```python
    existing = get_doc(db_name, doc_id)
    if existing:
        doc["_rev"] = existing["_rev"]
    ```

### Architecture Components
1.  **Flask REST API:** Serves UI and admin routes (`api/`).
2.  **MCP Server:** Provides tools for agents (`mcp_server.py`).
3.  **Vue UI:** Frontend dashboard (`ui/`).

### Common Tasks
- **Adding MCP Tool:**
  - Define in `mcp_server.py` with `@mcp.tool()`.
  - First argument MUST be `namespace: str`.
  - Validate `namespace` is a valid UUID.
- **Adding API Endpoint:**
  - Define in `api/routes.py`.
  - Use `@requires_auth`.
  - Validate input with Pydantic model.
  - Apply `bleach` sanitization to text inputs.
  - Return JSON responses with standard status codes.

### Troubleshooting
- **CouchDB:** Check if databases exist with `curl -u $COUCHDB_USER:$COUCHDB_PASSWORD http://localhost:5984/_all_dbs`.
- **Logs:** Check Docker logs with `docker compose logs -f moirai`.
- **Tests:** Use `-v` flag with pytest for verbose output.

