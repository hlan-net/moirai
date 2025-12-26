# Project Moirai: MCP-Powered Press Review Service

## Project Overview
Moirai is a GenAI-native press review platform. It has transitioned from a scheduled background service to an **agent-centric architecture** powered by the Model Context Protocol (MCP).

Instead of autonomous fetching, Moirai acts as a sophisticated data lake and synthesis engine that LLM agents use to analyze news, identify significant events, and track long-term trends across various namespaces.

## New User & Agent Flow
1.  **Ingestion:** An agent uses the `add_feed` tool via MCP to register RSS sources into a specific **Namespace** (GUID).
2.  **Collection:** The agent triggers `read_feed` to pull live articles.
3.  **Synthesis (Layer 1 - Events):** The agent analyzes raw articles and calls `add_event` to group related links into a named **Event** with a description.
4.  **Synthesis (Layer 2 - Trends):** The agent identifies patterns across events and calls `add_trend` to group events into a high-level **Trend**.
5.  **Review & Administration:** A human user accesses the Vue.js dashboard to review the agent's work, delete noisy data, or refine the groupings (removing specific links or events).

## Current Architecture
-   **Backend (API):** Flask REST API on port `8088`.
    -   **Security:** Enforces HTTP Basic Auth (`API_USERNAME` / `API_PASSWORD`).
    -   **Responsibility:** Serves the UI and provides administrative CRUD operations.
-   **MCP Server:** FastMCP SSE server on port `8090`.
    -   **Security:** Enforces **Namespace isolation** (GUID required for all data tools).
    -   **Tools:** `add_feed`, `list_feeds`, `read_feed`, `add_event`, `list_events`, `read_event`, `add_trend`, `list_trends`, `read_trend`.
-   **Frontend:** Vue.js 3 + TypeScript.
    -   **Layout:** 4-column admin view (Feeds, Articles, Events, Trends).
    -   **Features:** Cross-namespace review and item-level cleanup.
-   **Data Storage:** Apache CouchDB. Databases: `feeds`, `articles`, `events`, `trends`.

## Rewrite Progress
- [x] **Remove Scheduler:** Autonomous background tasks have been disabled.
- [x] **MCP Integration:** Stdio MCP server implemented and converted to HTTP/SSE.
- [x] **Namespace Security:** Implemented GUID-based data segregation in MCP tools.
- [x] **API Security:** Implemented HTTP Basic Auth for the Flask backend.
- [x] **UI Overhaul:** Implemented 4-column layout with Event/Trend management.
- [x] **Data Persistence:** Added `trends` database support and conflict handling.
- [ ] **Polishing:** Finalize UI styling and add namespace filtering to the dashboard.

## How to Build and Run
1.  **App & DB:** `docker compose up --build` (Port 8088).
2.  **MCP Server:** `python mcp_server.py` (Port 8090).