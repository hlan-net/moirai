# Moirai Architecture

## 1. Overview
Moirai is a GenAI-native press review platform designed for the Model Context Protocol (MCP) ecosystem. It operates on an **agent-centric architecture**: external AI agents (via MCP) or human administrators (via the UI) drive the ingestion and synthesis process rather than an autonomous internal scheduler.

The core abstraction is the **Hourglass**: articles are grains of sand (raw signal), and **Issues** are the patterns that emerge from observing that signal over time.

---

## 2. Core Components

### 2.1 API Service (Flask + Gunicorn)
- **Port:** `8088`
- **Role:** Stateless web server. Serves REST API endpoints for the UI and admin operations. Runs as a scalable `Deployment` in Kubernetes (multiple replicas supported).
- **Security:** JWT authentication. `@requires_auth` decorator on all protected routes.
- **Key Routes:**
  - `/api/feeds`, `/api/articles` — content management
  - `/api/issues` — issue management (CRUD + search)
  - `/api/stats` — aggregated statistics (via CouchDB MapReduce views)
  - `/api/chat` — chat interface endpoints
  - `/api/auth` — login / token management

### 2.2 Enrichment Worker (`run_worker.py`)
- **Role:** Long-running CouchDB changes-feed listener. Polls `feed_content/_changes`, parses raw feed bodies into structured articles, and stores them in the `articles` database.
- **Concurrency:** Single instance only (hardcoded `replicas: 1` in Kubernetes). Runs as a dedicated `Deployment` separate from the API.

### 2.3 Scheduler (`run_scheduler.py`)
- **Role:** Periodic feed fetcher. Iterates over all registered feeds, triggers a `FetchFeedTask` per feed (writes raw content to `feed_content`), then exits.
- **Operation:** Runs as a Kubernetes `CronJob` (configurable schedule, default every 10 minutes). Can be triggered manually: `docker compose run --rm api python run_scheduler.py`.

### 2.4 MCP Server (FastMCP / Starlette)
- **Port:** `8090`
- **Transport:** SSE (Server-Sent Events)
- **Role:** Exposes tools for LLM agents to interact with the system.
- **Security:** Namespace (userspace GUID) required on all data tools.
- **Tools:**
  - `add_feed`, `read_feed`, `list_feeds`, `list_articles` — ingestion & collection
  - `forge_issue` — create a new Issue from observed signal (Clotho)
  - `measure_issue` — update an Issue's weight and longevity scale (Lachesis)
  - `seal_issue` — mark an Issue as eternal / passed (Atropos)
  - `list_issues` — query active or eternal issues by longevity

### 2.5 Frontend (Vue.js 3)
- **Role:** Administrative dashboard for human operators.
- **Features:** Feeds, articles, issues management; aggregated stream view; chat interface; namespace filtering.
- **Contextual chat:** Dashboard cards can open contextual chat (article/issue/feed), persisted to `chat_history` and resumable from `/chat`.
- **Issue raise wizard:** Article contextual chat includes a guided issue-raise flow with clarifying questions for generic/reusable issue framing.
- **Technology:** Vue 3, TypeScript, Pinia, Vite.

### 2.6 Nginx (Reverse Proxy)
- **Role:** Single entry point. Routes `/api/*` and `/mcp/*` to the API service, everything else to the UI static files.
- **Timeouts:** `/api` proxy timeouts are tuned for longer chat/tool-assisted operations.

### 2.7 Data Storage (CouchDB)
- **`feeds`** — RSS source URLs and metadata.
- **`feed_content`** — raw fetched feed bodies (intermediate store).
- **`articles`** — parsed, enriched news items.
- **`issues`** — emergent issues (unified store, replaces legacy `events` and `trends`).
- **`config`** — system configuration and worker state (e.g., `enrichment_last_seq`).
- **`chat_history`** — agent conversation history.
  - Includes contextual session metadata for dashboard-origin chats.
- **`users`** — user accounts.

---

## 3. Data Model: Issues

An **Issue** is a pattern deduced from the stream of articles. It is defined by its longevity scale and lifecycle state.

```json
{
  "_id": "uuid",
  "logos": "The headline/essence of the deduction",
  "description": "text",
  "userspace": "guid",
  "longevity": "transient | temporal | epic",
  "status": "active | eternal",
  "premises": [
    { "type": "message | issue", "id": "uuid" }
  ],
  "born_at": "timestamp",
  "passed_at": "timestamp | null"
}
```

**Longevity scale:**
- `transient` — high-frequency burst; appears and fades quickly.
- `temporal` — mid-frequency sustained pattern; a coherent debate or movement.
- `epic` — low-frequency foundational arc; a standing wave of history.

**Lifecycle:**
- `active` — the Issue IS; it is currently modulated by new signal.
- `eternal` — the Issue WAS; it has passed and is an immutable historical record.

---

## 4. Data Flow

```
Scheduler (CronJob)
  → FetchFeedTask per feed
  → writes raw body to feed_content DB

EnrichmentWorker (Deployment, 1 replica)
  → polls feed_content/_changes
  → ArticleProcessor parses & enriches
  → writes structured articles to articles DB

LLM Agent (via MCP)
  → reads articles with list_articles
  → forge_issue / measure_issue / seal_issue
  → writes/updates issues DB

UI / API
  → human operator reviews feeds, articles, issues
  → interacts with agent via chat
```

---

## 5. Security
- **Authentication:** JWT tokens issued by `/api/auth/login`.
- **Isolation:** All data operations require a `userspace` GUID, preventing data leakage between agent contexts.
- **Input sanitisation:** All text inputs sanitised with `bleach.clean()`.
- **Rate limiting:** Flask-Limiter (disabled in local dev via `DISABLE_RATE_LIMIT`).
- **Rate-limit keying:** auth-aware key derivation is used to reduce false throttling when clients are behind shared proxies.

---

## 6. Deployment

### Docker Compose (local development)
```bash
docker compose up --build
```
Services: `api`, `worker`, `nginx`, `ui`, `mcp-server`, `couchdb`, `redis`.

### Kubernetes (Helm)
```bash
helm upgrade --install moirai oci://ghcr.io/hlan-net/charts/moirai -f values.yaml --namespace moirai
```
- `api` runs as a scalable `Deployment` (`api.replicaCount` in `values.yaml`).
- `worker` runs as a single-replica `Deployment`.
- `scheduler` runs as a `CronJob` (`scheduler.schedule` in `values.yaml`, default `*/10 * * * *`).
