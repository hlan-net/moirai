# Project Moirai: MCP-Powered Press Review Service

## Project Overview
Moirai is a GenAI-native press review platform. It has transitioned from a scheduled background service to an **agent-centric architecture** powered by the Model Context Protocol (MCP).

Instead of autonomous fetching, Moirai acts as a sophisticated data lake and synthesis engine that LLM agents use to analyze news, identify significant events, and track long-term trends across various userspaces.

## New User & Agent Flow
1.  **Ingestion:** An agent uses the `add_feed` tool via MCP to register RSS sources into a specific **Userspace** (GUID).
2.  **Collection:** The agent triggers `read_feed` to pull live articles.
3.  **Synthesis (Layer 1 - Events):** The agent analyzes raw articles and calls `add_event` to group related links into a named **Event** with a description (stored as a transient Issue).
4.  **Synthesis (Layer 2 - Trends):** The agent identifies patterns across events and calls `add_trend` to group events into a high-level **Trend** (stored as a temporal Issue).
5.  **Review & Administration:** A human user accesses the Vue.js dashboard to review the agent's work, delete noisy data, or refine the groupings (removing specific links or events).

## Current Architecture
-   **Backend (API):** Flask REST API on port `8088`.
-   **Security:** Enforces HTTP Basic Auth (`ADMIN_USERNAME` / `ADMIN_PASSWORD`).
    -   **Responsibility:** Serves the UI and provides administrative CRUD operations.
-   **MCP Server:** FastMCP SSE server on port `8090`.
    -   **Security:** Enforces **Userspace isolation** (GUID required for all data tools).
    -   **Tools:** `add_feed`, `list_feeds`, `read_feed`, `forge_issue`, `list_issues`, `read_issue` plus event/trend aliases (`add_event`, `list_events`, `read_event`, `add_trend`, `list_trends`, `read_trend`).
-   **Frontend:** Vue.js 3 + TypeScript.
    -   **Layout:** 4-column admin view (Feeds, Articles, Events, Trends).
    -   **Features:** Cross-userspace review and item-level cleanup.
-   **Data Storage:** Apache CouchDB. Databases: `feeds`, `articles`, `issues`.

## Documentation Architecture
Moirai follows a multi-tier documentation structure to balance high-level oversight with detailed technical specifications:

### 1. Root Meta-Documents (CAPS)
High-level project metadata and foundational guidance live in the root directory. These files use **ALL CAPS** naming for visibility and adherence to standard repository conventions.
- `README.md`: Project overview and quick start.
- `GEMINI.md`: Foundational mandates and documentation conventions.
- `ROADMAP.md`: The master orchestration document. It outlines planned improvements and release versions, referencing detailed docs in `/docs`.
- `AGENTS.md`: Overview of the agentic ecosystem and MCP integration.
- `LICENSE`, `CHANGELOG.md`, `EXAMPLES.md`.

### 2. Feature & Concept Documents (lowercase kebab-case)
Detailed technical designs, functionalities, user stories, and architectural concepts live in the `docs/` directory. 
- **Naming:** These files use **lowercase kebab-case** (e.g., `agentic-improvements.md`) for better readability in file listings.
- **Content:** Each document should focus on a specific concept or feature from the project's goal-oriented perspective.
- **Referencing:** The root-level `ROADMAP.md` should serve as the primary entry point, linking to these detailed documents as features are planned and implemented.

## Development Lifecycle
1.  **App & DB:** `docker compose up --build` (Port 8088).
2.  **MCP Server:** Activate Miniforge env, then `mamba run -n moirai python mcp_server.py` (Port 8090).

### Local Docker build metadata (non-GitHub builds)
Use `BUILD_NUMBER` during local image builds so About shows an explicit build label (instead of `build unknown`/empty):

```bash
BUILD_LABEL="CI $(date '+%Y-%m-%d %H:%M') build"

docker build -f api/Dockerfile \
  --build-arg BUILD_NUMBER="$BUILD_LABEL" \
  -t rgsty.hlan.net/moirai:main .

docker build -f ui/Dockerfile ui \
  --build-arg BUILD_NUMBER="$BUILD_LABEL" \
  -t rgsty.hlan.net/moirai-ui:main .
```
