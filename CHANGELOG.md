# Changelog

Notable design decisions and significant changes to the Moirai project, in reverse chronological order. This is a high-level log — not a commit-by-commit history. See git log for fine-grained detail.

---

## [Unreleased / In Development]

### Re-annotation at backlog scale (#273)
`scripts/reannotate_outdated.py` was shaped for hundreds of articles; production had 25 008 behind version 2 at ~18 s each, with no count, progress or ETA. The script now reports the outdated count up front and the remaining count at the end (from a new `annotation/by_version` reduce view, seconds instead of an 11-minute listing), logs `done/total, rate, ETA` every `--progress-every` articles, and accepts `--concurrency N` (default 1, unchanged behaviour). `--dry-run` now only counts; add `--list` for ids. The docs state what was always true: finished articles are stamped and never revisited, so the job can be stopped and resumed at will.

### Fixes
- API image sets `PYTHONPATH=/app`, so scripts under `scripts/` import `api` and `tasks` however they are started. Documented commands use the module form, e.g. `python -m scripts.reannotate_outdated` (the path form failed with `ModuleNotFoundError: No module named 'api'` in 0.9.0).

---

## [v0.9.0] — 2026-10-22

### AISA in-cluster inference proxy as an LLM provider
`aisa` joins ollama, openai and gemini as a fourth, additive LLM provider. AISA is an in-cluster OpenAI-compatible proxy that reconciles a Secret with the `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL` contract into the app namespace. Direct providers and their keys are untouched and never routed through AISA.

- Resolution lives in `api/llm/aisa.py` (`AISA_*` env vars, with the standard `OPENAI_*` Secret names accepted as fallbacks).
- Helm: `aisa.enabled`, `aisa.secretName`, `aisa.defaultModel` and an optional Reloader annotation for key rotation. Disabled renders unchanged.
- UI: AISA option in Settings and the chat provider selectors; models are listed without a user key.
- See `docs/llm-configuration.md`.

### Annotation: closed topic vocabulary (#249, #268)
Production tagged a Finnish death notice `politics` / `security` from a single identity term. Topics are now restricted to a fixed `TOPIC_VOCABULARY` (with aliases such as `tech` → `technology`), and the prompt states that topics describe what the article is about, not the group membership of people mentioned. Unknown labels are dropped, falling back to `general`.

- Every annotation stores `annotation_version` (now `2`).
- `scripts/reannotate_outdated.py` regenerates annotations behind the current version (`--dry-run`, `--limit`, `--userspace`). Run it in the worker pod after deploying; the worker never revisits already-annotated articles.

### Docs
- Roadmap entry and design for Stream sections (`docs/stream-sections.md`, #266).

---

## [v0.5.2] — 2026-02-24

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

### MCP Metrics Port Split
The MCP server now exposes its Prometheus metrics on a dedicated port, separate from the main SSE endpoint.

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
