# Changelog

Notable design decisions and significant changes to the Moirai project, in reverse chronological order. This is a high-level log — not a commit-by-commit history. See git log for fine-grained detail.

---

## [Unreleased / In Development]

### Single implicit userspace, step 3: UI and REST API
The Agents and Sessions pages no longer ask for a userspace; the REST API fills in the deployment default. `/api/agents`, `/api/sessions` (non-admin callers) and `/api/approvals/pending` default a missing `userspace` to it, and `POST /api/agents` stores it when the payload has none. Access checks go through `can_access_userspace()`: any authenticated user may use the default userspace, other (legacy) userspaces stay limited to their owner and admins. Chat resolves its LLM config and MCP tool scope from the default userspace instead of the caller's user id, so a user who signs in through GitHub, Google or Entra works on the same data as the admin account.

### Single implicit userspace, step 2: optional MCP `userspace`
The `userspace` argument of the feed, issue, search, annotation, staleness and social-export MCP tools is now optional. When it is empty, `resolve_userspace()` in `mcp_service/core.py` substitutes the deployment default (`DEFAULT_USERSPACE`, or the only userspace document), so MCP clients no longer need to know a UUID. Agent-config tools still require it. `social_export.py` imported `validate_userspace` from the wrong module; the import is fixed (the module is still not registered in `mcp_service/main.py`).

### Model catalog for chat, agents and social export
The catalog's purposes now cover every LLM call: `event_synthesis` (event-creating and -updating agents, with per-call fallback through the listed entries), `chat` and `social_export` (first entry). `resolve_llm_config(userspace, purpose)` returns the catalog entry as an `llm_config` dict and falls back to the userspace document when the purpose is not listed, so deployments without a catalog are unchanged. Agent `llm_model_config`, stored but ignored until now, can pin one entry with `catalog_entry`. Session logs redact API keys inside fallbacks too.

### Model catalog for annotation
Which model served which job was spread over env vars with purpose-specific names (`ANNOTATION_OLLAMA_BASE_URL`, `MODEL_NAME`, ...), and the dedicated annotation tier could only be Ollama. `api/llm/catalog.py` adds a deployment-wide catalog: named entries (provider, endpoint, model, capabilities, languages) and purposes mapping to ordered fallback lists, set in Helm as `llm.catalog` / `llm.purposes` and read from `LLM_CATALOG_FILE`. The annotator now resolves its backends through the `annotation` purpose, so any provider, including AISA, can be a tier. Without a catalog the legacy env vars are synthesised into the same entries, and the rendered chart is unchanged. Chat and agents move onto purposes in a follow-up; Moirai is single-tenant, so there is no per-userspace model layer.

### Single implicit userspace, step 1
Moirai was designed multi-tenant, but it runs as one person's deployment and the dashboard REST API never filtered by userspace anyway. Multi-tenancy is being dismantled: everything belongs to one default userspace, and LLM configuration becomes deployment-level (AISA handles inference cost protection). This first step adds `get_default_userspace()` (`DEFAULT_USERSPACE` env, Helm `defaultUserspace`, falling back to the only document in `userspaces`). Scheduled ingestion now stamps articles with it: articles stored by the enrichment worker had no `userspace` field, so `ON_NEW_ARTICLE` agents silently skipped every article not fetched through the MCP `read_feed` tool. The orchestrator also routes any article still lacking a `userspace` (older articles, or a failed lookup at write time) to the default userspace. The unreachable per-owner `GET /api/userspaces` handler in `api/userspace_routes.py` (shadowed by the one in `api/routes.py`) is removed.

---

## [v0.9.1] — 2026-10-23

### AISA key read from a mounted Secret (#272)
The chart wired the AISA key as the env var `AISA_API_KEY`, which Kubernetes never refreshes: a week after an AISA rotation (the grace period), every call would fail 401 until the pods restarted. The only remedy was `aisa.reloader`, which needs Stakater Reloader in the cluster. With `aisa.enabled`, the chart now mounts the Secret into api, worker, mcp-server and scheduler pods and sets `AISA_API_KEY_FILE` (`aisa.keyFile: true` by default, mount path `aisa.keyMountPath`); `api/llm/aisa.py` already re-reads the file on every request. `aisa.keyFile: false` keeps the env form. The README names the Reloader dependency.

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
