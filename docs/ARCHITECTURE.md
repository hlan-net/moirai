# Moirai Architecture

## 1. Overview
Moirai is a GenAI-native press review platform designed for the Model Context Protocol (MCP) ecosystem. It has transitioned from a traditional autonomous scheduler to an **agent-centric architecture**.

Instead of the system autonomously deciding what to fetch and process, Moirai acts as a sophisticated data lake and synthesis engine. External AI agents (via MCP) or human administrators (via the UI) drive the ingestion and synthesis process.

## 2. Core Components

### 2.1 Backend (Flask API)
-   **Port:** `8088`
-   **Role:** Serves the Web UI, handles data persistence, provides administrative REST APIs, and runs background services.
-   **Background Services:**
    -   **Scheduler:** Periodically triggers feed collection.
    -   **EnrichmentWorker:** Monitors the CouchDB `_changes` feed to asynchronously process and enrich raw feed content into structured articles.
-   **Security:** HTTP Basic Auth (`API_USERNAME` / `API_PASSWORD`).
-   **Key Routes:**
    -   `/api/feeds`, `/api/articles` - Content management
    -   `/api/stats` - Global system statistics via MapReduce views
    -   `/api/events`, `/api/trends` - Synthesis management
    -   `/api/chat` - Internal chat interface endpoints

### 2.2 MCP Server (FastMCP)
-   **Port:** `8090`
-   **Transport:** SSE (Server-Sent Events)
-   **Role:** Exposes tools for LLM Agents to interact with the system.
-   **Security:** Namespace isolation (GUID required for data tools).
-   **Tools:**
    -   `add_feed`, `read_feed`, `list_feeds`, `list_articles` - Ingestion & Collection
    -   `add_event`, `list_events`, `read_event` - Level 1 Synthesis
    -   `add_trend`, `list_trends`, `read_trend` - Level 2 Synthesis

### 2.3 Frontend (Vue.js)
-   **Role:** Administrative dashboard for humans.
-   **Features:**
    -   4-column layout: Feeds → Articles → Events → Trends
    -   Chat interface for interacting with the Agent
    -   Namespace filtering and management
-   **Technology:** Vue 3, TypeScript, Vite.

### 2.4 Data Storage (CouchDB)
-   **Databases:**
    -   `feeds`: RSS source URLs and metadata.
    -   `articles`: Fetched news items with auto-detected language.
    -   `feed_content`: Raw RSS/Atom content (collection layer).
    -   `events`: Grouped articles (Level 1 synthesis).
    -   `trends`: Grouped events (Level 2 synthesis).
    -   `config`: System configuration and worker state.
-   **Integrity:** `validate_doc_update` functions enforce schema at the database layer.
-   **Analytics:** Pre-aggregated statistics using MapReduce views (`articles/stats`, `feeds/health`).

## 3. Data Flow

### 3.1 Agent Synthesis Flow
1.  **Ingestion:** Agent uses `add_feed` to register sources.
2.  **Collection:** Agent uses `read_feed` or `list_articles` to access content.
3.  **Event Synthesis:** Agent correlates articles into `Events` using `add_event`.
4.  **Trend Synthesis:** Agent correlates events into `Trends` using `add_trend`.

### 3.2 User Review Flow
1.  User opens Dashboard.
2.  User reviews generated Events and Trends.
3.  User prunes irrelevant Articles or invalid groupings using the UI.
4.  User interacts with the Agent via the Chat page to refine data.

## 4. Security
-   **Authentication:** HTTP Basic Auth for API and UI.
-   **Isolation:** Data segmentation via Namespaces (GUIDs) allows multiple distinct analysis contexts to coexist.

## 5. Deployment
-   **Containerization:** Docker & Docker Compose.
-   **Orchestration:** Helm charts available for Kubernetes deployment.
