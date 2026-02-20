# Changelog

Notable design decisions and significant changes to the Moirai project, in reverse chronological order. This is a high-level log — not a commit-by-commit history. See git log for fine-grained detail.

---

## [Unreleased / In Development]

### Service Decoupling (Scheduler and Worker split from API)
The API process previously launched the enrichment worker and scheduler as background threads via a Gunicorn `on_starting` hook. This prevented the API from being scaled horizontally.

The background tasks are now separate processes with dedicated entrypoints:
- `run_worker.py` — long-running enrichment worker (CouchDB changes-feed listener).
- `run_scheduler.py` — single-run feed fetcher, designed to be called by a CronJob.

In Docker Compose a `worker` service runs `run_worker.py`. In Kubernetes a `worker` Deployment (single replica) and a `scheduler` CronJob handle the same responsibilities. The API Deployment is now stateless and can be scaled freely via `api.replicaCount`.

### Issues Model ("The Fates" — 2nd iteration domain model)
The `events` and `trends` abstractions were replaced with a unified **Issue** model. Rather than a fixed two-level hierarchy (events group articles, trends group events), Issues are now emergent observations with a **longevity scale**:

- `transient` — high-frequency, short-lived signal bursts.
- `temporal` — sustained patterns that persist across time.
- `epic` — foundational, long-running arcs.

Issues have a **lifecycle**: `active` (currently observed) → `eternal` (passed; immutable historical record).

MCP tools reflect this model: `forge_issue` (Clotho), `measure_issue` (Lachesis), `seal_issue` (Atropos), `list_issues`. Legacy `add_event` / `add_trend` tool aliases are preserved for compatibility and redirect to the `issues` database with appropriate longevity values.

Data is stored in a unified `issues` CouchDB database.

---

## [v0.4.0] — 2025

- Renamed namespaces to **userspaces**.
- UI/API container split: dedicated `api` and `ui` Docker images, coordinated by an Nginx reverse proxy.
- Helm chart restructured to support independent `api`, `ui`, and `nginx` deployments.
- JWT authentication replacing HTTP Basic Auth.
- Async enrichment pipeline: `FetchFeedTask` stores raw content only; `EnrichmentWorker` processes it asynchronously via CouchDB `_changes`.
- CouchDB MapReduce views for stats (`by_language`, feed `health`).

## [v0.3.x]

- MCP server introduced (FastMCP / SSE).
- Agent-centric architecture: external agents drive ingestion and synthesis via MCP tools.
- Multi-namespace (userspace) isolation.

## [v0.2.0]

- Events and Trends synthesis layer added.
- CouchDB as primary data store.

## [v0.1.0]

- Initial release: RSS feed ingestion, article storage, Flask API, Vue.js dashboard.
