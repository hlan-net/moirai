# Moirai - MCP-Powered GenAI Press Review Service

Moirai is a GenAI-native press review platform designed for the Model Context Protocol (MCP) ecosystem. It allows AI agents to aggregate RSS feeds, synthesize them into "Events," and track long-term "Trends" across isolated namespaces.

**Note:** This project has transitioned from an autonomous scheduled service to an **agent-centric architecture**.

## Project Overview

Moirai consists of three core components:
-   **Admin UI:** A 4-column Vue.js dashboard for reviewing and pruning Feeds, Articles, Events, and Trends.
-   **REST API:** A Flask backend that handles data persistence and administrative tasks (secured via HTTP Basic Auth).
-   **MCP Server:** A FastMCP-powered SSE server that provides tools for LLM agents to fetch and synthesize news data.

### Data Model Concepts

**Feeds** → **Articles** → **Events** → **Trends**

-   **Feed:** An RSS/Atom source URL (e.g., `https://example.com/feed.xml`)
-   **Article:** A single news item fetched from a feed (title, link, summary, published date)
-   **Event:** A named grouping of related articles describing a single significant occurrence
    - Example: "Company X Announces Merger" (groups articles from different sources about the same merger announcement)
    - Example: "New Climate Policy Announced" (links articles covering the same policy from various outlets)
    - Example: "Major Security Vulnerability Discovered" (connects articles about the same CVE disclosure)
-   **Trend:** A higher-level pattern connecting multiple related events over time
    - Example: "Remote Work Adoption" (links events like "Tech Company Goes Fully Remote", "Office Space Market Decline", "Collaboration Tool Growth")
    - Example: "Electric Vehicle Market Growth" (connects events about new EV models, charging infrastructure, and manufacturer investments)
    - Example: "Privacy Legislation Changes" (groups events like GDPR updates, state privacy laws, and data breach regulations)

## Project Structure
```
.
├── api              # RESTful API handlers (Flask)
├── ui               # Admin Dashboard (Vue.js 3 + TypeScript)
├── mcp_server.py    # MCP SSE Server (Agent Tools)
├── tasks            # Core logic for RSS parsing and DB init
├── Dockerfile       # Multi-stage build for API + UI
├── docker-compose.yml # Full stack setup (App + CouchDB)
└── helm             # Kubernetes deployment charts
```

## Setup & Running

For detailed examples on how to test the API and MCP tools, see [EXAMPLES.md](./EXAMPLES.md).

### 1. Run the Application Stack (UI + API + Database)
The easiest way to run the core stack is via Docker Compose:
```bash
docker compose up --build
```
- **Admin UI:** `http://localhost:8088`
- **REST API:** `http://localhost:8088/api`
- **MCP Server:** `http://localhost:8090/sse`
- **Credentials:** Configurable via `API_USERNAME`/`API_PASSWORD` env vars.

### 2. Run the MCP Server (Optional Local Run)
The MCP server is already included in `docker compose up`. To run it manually (for local debugging outside Docker):
```bash
# Ensure dependencies are installed
pip install -r requirements.txt

# Start the server
python mcp_server.py
```
- **Transport:** SSE (HTTP)
- **Endpoint:** `http://localhost:8090/sse`

### 3. GenAI Chat (Experimental)
A built-in Chat interface allows you to interact with an Agent that has access to the MCP tools.
- **Access:** Click "Chat" in the top navigation bar.
- **Configuration:** Go to "Settings" to configure the LLM Model (default: `gemma3:1b`, recommend `llama3.1` for tool support).
- **Requirements:** An OpenAI-compatible LLM endpoint (e.g., Ollama running locally).
  - By default, it connects to `http://host.docker.internal:11434/v1`.
  - Ensure you have pulled the model (e.g., `ollama pull llama3.1`).

### 4. RSS Feed
The aggregated article stream is available as a public RSS feed:
- **URL:** `http://localhost:8088/api/stream.rss`
- **Features:**
  - All articles sorted by publication date (newest first)
  - Event and Trend labels included as `<category>` tags
  - Source feed information in `<source>` element
  - Default limit: 100 items (configurable with `?limit=N` query parameter)
- **No authentication required** - RSS feeds are publicly accessible

> **Helm users:** the chart now deploys both the admin API/UI and the MCP SSE server when `mcpServer.enabled` (default). Disable or customize it by overriding the `mcpServer` block in `values.yaml`.

### 4. Deploying with Helm

You can install the chart directly from our OCI registry:

```bash
helm install moirai oci://ghcr.io/hlan-net/charts/moirai --version 0.2.23
```

Or add dependencies manually if building locally:

```bash
helm repo add couchdb https://apache.github.io/couchdb-helm
helm dependency update helm/
helm install moirai helm/
```

- **Isolation:** All data tools require a `namespace` (GUID).

## Agent Synthesis Flow

Agents use MCP tools to build a layered understanding of news:

1.  **Ingest:** `add_feed` → Register RSS sources
2.  **Fetch:** `read_feed` → Retrieve latest articles from feeds
3.  **Synthesize Events:** `add_event` → Analyze articles and group related ones into named Events (single occurrences covered by multiple sources)
4.  **Synthesize Trends:** `add_trend` → Identify patterns across Events to form Trends (broader themes emerging from multiple related events)

## Administrative Flow
Human editors can use the Dashboard to:
-   Delete noisy or irrelevant **Articles**.
-   Prune links from **Events** to improve quality.
-   Dissolve **Trends** that are no longer accurate.

## License
This project is licensed under the MIT License.
