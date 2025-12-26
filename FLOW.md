# Moirai User Flow & Rewrite Status

## 1. Agent Interaction Flow (The "Synthesis Chain")
The primary user of Moirai's logic is an AI Agent using the MCP protocol.

1.  **Identity:** Agent identifies the target `namespace` (GUID).
2.  **Lookup:** Agent calls `list_feeds(namespace)` to see active sources.
3.  **Fetch:** Agent calls `read_feed(url)` to get the latest article summaries.
4.  **Event Creation:** Agent identifies a cluster of news (e.g., "Python 3.14 Release") and calls:
    `add_event(name="Python 3.14", desc="New features...", article_links=[...], namespace="GUID")`
5.  **Trend Mapping:** Agent looks at events over time and calls:
    `add_trend(name="Python Evolution", desc="Trend of faster releases...", event_ids=[...], namespace="GUID")`

## 2. Human Administrative Flow
The human user acts as the "Editor-in-Chief" via the Web UI.

1.  **Access:** User logs in via HTTP Basic Auth.
2.  **Monitor:** User views the 4 columns to see real-time updates from the Agent.
3.  **Prune:** 
    *   Delete irrelevant **Articles**.
    *   Remove biased **Feeds**.
    *   Refine **Events** by removing low-quality links.
    *   Dissolve **Trends** that are no longer relevant.

## 3. Implementation Progress (Rewrite Status)

### Phase 1: Core Clean-up (Completed)
*   Decommissioned the old Python `scheduler.py`.
*   Fixed CouchDB initialization typos and improved connection resilience.
*   Implemented `ArticleProcessor` to handle real-world RSS XML.

### Phase 2: Security & Isolation (Completed)
*   **API Auth:** Added mandatory `API_USERNAME` and `API_PASSWORD` check to all Flask routes.
*   **MCP Namespacing:** All data tools now require a GUID to ensure agents don't leak data between contexts.

### Phase 3: MCP Transformation (Completed)
*   Built `mcp_server.py`.
*   Implemented SSE (HTTP) transport for network-accessible agent tools.
*   Added specific tools for "Trends" to complete the 3-layer data model.

### Phase 4: UI Modernization (Completed)
*   Transitioned from 3 to 4 columns.
*   Added CRUD support for the new Trend model.
*   Implemented item-level deletion (links inside events, events inside trends).

## Next Steps
- Implement a Namespace selector in the UI.
- Add Batch actions for article deletion.
- Dockerize the MCP server for a unified stack.
