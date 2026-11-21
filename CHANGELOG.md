# Changelog

Notable design decisions and significant changes to the Moirai project, in reverse chronological order. This is a high-level log — not a commit-by-commit history. See git log for fine-grained detail.

---

## [Unreleased / In Development]

### CouchDB connections are reused (#353)
The API and the MCP server send CouchDB requests through one pooled `requests.Session` per process instead of opening a connection per call. In production a hand-made, stale EndpointSlice had left three dead addresses behind the CouchDB service name, and with a new connection per request about half of all calls waited ~3 s on one of them; the slice has been removed, and connection reuse keeps a single bad address from taxing every request.

### passlib replaced by bcrypt (#337)
Password hashing moves from `passlib.hash.bcrypt` to the `bcrypt` package directly (`api/passwords.py`). passlib 1.7.4 is unmaintained, breaks with bcrypt 5 and imports the `crypt` module that Python 3.13 removed, which was the last blocker for 3.13. Stored hashes are the same `$2b$` format and keep verifying; passwords longer than 72 bytes are truncated as passlib did.

### Dependency updates
Supersedes Dependabot PRs #333–#338, #340–#342 and #348. Major versions: openai 3.53, google-genai 3.4 (with websockets 17.4, which google-genai 1.x capped), redis-py 8.1 and the Redis 8 image, gunicorn 27, structlog 26, python-dateutil 4, bcrypt 5. Minor and patch: pydantic 2.14, starlette 1.10, uvicorn 0.54 and others. `tenacity` stays at 9.1.4 because google-genai 3.4 requires `<9.2`. ruff moves to 0.17.5 with its rule selection pinned to the previous defaults (`E4`, `E7`, `E9`, `F`): 0.17 widened the defaults to several hundred rules. `mcp` stays on 1.30; the 2.x migration is tracked separately.

The chart's default CouchDB image is 3.5.3 (#355); an existing deployment keeps its version until upgraded by the procedure in that issue.

---

## [v0.11.2] — 2026-11-20

### Stream page shows articles again (#343)
Since v0.11.0 the Stream page listed no articles in any section. `/api/stream.rss` wrote the request URL into the feed's `<atom:link href>` unescaped, so the `&` between two query parameters made the document malformed XML, and the page always sends two (`limit` and `section`). Every value interpolated into the channel header is now escaped, and the route tests parse the feed as XML for each section with the page's own query. The Redis cache now holds only the feed's items, under new `stream_rss_items…` keys: the channel header, which carries the request's own URL, is built for every response, so a cached feed no longer answers with the self link of whichever request filled the cache, and no malformed document cached by v0.11.1 is served after the upgrade.

### Python pins in requirements files (#317)
The pip pins move from `environment.yml` / `environment-prod.yml` into `requirements.txt` (runtime) and `requirements-dev.txt` (runtime plus test and lint tooling); both conda environments install from them. Dependabot's pip ecosystem reads these files, which it could not do with the environment files, so Python updates and advisories now arrive as PRs. No version changes.

### Build and CI hardening (#320)
Workflows install UI dependencies with `yarn install --immutable` and lifecycle scripts disabled, run Playwright through the locked dependency instead of `npx`, and have job timeouts. `api/Dockerfile` drops a no-op `pip install` and asserts the mode of `/tmp` instead of re-granting it. SonarCloud vulnerabilities go from 21 to 0.

### Docs (#322)
`docs/releasing.md` describes the release flow in use (release PR into `main`, tag, image build, GitHub Release, deploy, verify). `ROADMAP.md` lists what shipped in v0.9–v0.11.

---

## [v0.11.1] — 2026-11-20

### Re-filed articles without annotations are annotated
In v0.11.0 the annotation worker skipped every stored article that the section backfill re-filed, so legacy articles that had never been annotated stayed that way. It now skips only those that already carry annotations; the rest go through the normal annotation path on the first worker start after the upgrade (one LLM call per unannotated stored article, once). `store_annotation` carries the re-filing stamp over to the revision it writes, so annotating a backlog article still does not dispatch `ON_NEW_ARTICLE` agents for it.

### Python 3.12 (#315)
The backend moves from Python 3.10, which reached end of life in October 2026, to 3.12. Both conda environments, the ruff target and the image-pruning paths in `api/Dockerfile` follow. No dependency pins change; unpinned transitive packages that 3.10 held back (filelock, dnspython) resolve to their fixed releases. 3.13 is blocked by `passlib` 1.7.4, which imports the removed `crypt` module. Local environments need recreating from `environment.yml`.

### CI tests the pinned dependency versions (#316)
`ci.yml` and `security.yml` reinstalled `google-genai` 1.3.0 and `google-auth` 2.38.0 with pip after creating the conda environment, below the pinned 1.7.0 and 2.49.1. The step is gone; CI prints the versions it resolved.

### Formatting is enforced (#314)
The codebase is formatted once with `black` and `prettier`, and CI now fails on unformatted code (`black --check`, `prettier --check`). Pre-commit pins black and ruff to the versions in `environment.yml`; the `ruff-format` hook is dropped because it and black reformat each other's output.

---

## [v0.11.0] — 2026-11-20

### Stream sections (#266)
The Stream page is split into four newspaper-style tabs: Top stories (open on load), Sports, Culture and Business. This is a fixed editorial split of the flow, not a reader-composed filter; the Stream model (no search, no inbox semantics) is unchanged. Every article gets exactly one `section` at ingestion (`tasks/sections.py`): a section-specific feed category wins, then the article URL (`hs.fi/urheilu/…`, `kauppalehti.fi`), then the closed annotation topic vocabulary from #249, else `main`. The deciding signal is stored as `section_source` so the asynchronous annotation never overrides a feed or URL decision. `GET /api/stream.rss?section=` filters the stream, each item carries `<category domain="section">`, the Redis cache is keyed per section and a `(section, published)` Mango index is created at startup; the unparameterised endpoint is unchanged apart from the added category. Admins pick a feed's section from a dropdown on the Feeds column (`PUT /api/feeds/<id>` accepts `category`). Existing articles are filed by a backfill (`scripts/backfill_sections.py`) that the worker runs in the background at every start; it pages through the database, writes only changed articles with `_bulk_docs` and retries write conflicts.

Re-filing a stored article is not a new article. The backfill and the feed re-file stamp the revision they write (`section_rewrite_gen`), and the two `articles/_changes` consumers, the agent orchestrator and the annotation worker, skip exactly that revision. Without it the first worker start after the upgrade would have dispatched every `ON_NEW_ARTICLE` agent over the whole backlog. Changing a feed's category re-files its stored articles whether the change comes through `PUT /api/feeds/<id>` or the MCP `update_feed_category` tool. `PUT /api/feeds/<id>` now rejects a body with none of `title`, `new_url`, `category`.

### Stream page uses the stream.rss cache (#308)
`GET /api/stream.rss` was cached in Redis only for `limit=100`, but the Stream page requests `limit=200`, so every poll and tab switch queried CouchDB. The cache key now comes from `stream_cache_key(section, limit)` over a closed set of limits (100 and 200), and `STREAM_CACHE_KEYS` lists every combination so ingestion, annotation, deletion and re-filing invalidate them all.

### Dependency updates (#310)
Supersedes Dependabot PRs #303–#307: axios 1.21.1, marked 18.2.0, vue-router 5.5.0, `@vitejs/plugin-vue` 6.0.11, prettier 3.10.1, vite 8.3.8 and the miniforge3 26.9.4-2 builder image.

---

## [v0.10.2] — 2026-11-05

### Security and dependency updates (#297)
Supersedes Dependabot PRs #290–#296 (axios, marked, follow-redirects, UI dev tooling, nginx / debian / miniforge3 base images) and fixes Python advisories that Dependabot cannot raise PRs for, because its pip ecosystem does not read `environment*.yml`. Python pins move to the newest releases that still support Python 3.10: mcp 1.30.0 (stays on 1.x), starlette 1.7.0, PyJWT 2.15.1, cryptography 50.0.2 (with msal 1.39.0 and atproto 0.0.73, whose caps blocked it), requests 2.34.2, bleach 6.4.0, opentelemetry 1.45.2 / 0.66b2. The UI drops the deprecated `@types/dompurify` stub and refreshes node-gyp, which removes the vulnerable glob / minimatch chain; `yarn npm audit` is clean. Transitive filelock and dnspython fixes need Python 3.11 and remain open.

This release also carries the v0.10.1 cleanup paging fix (#288), whose images were never built because v0.10.1 was not tagged.

---

## [v0.10.1] — 2026-10-31

### Fixes
- Article cleanup reads the `articles` database in pages of 1000 instead of one `_all_docs?include_docs=true` request (#288). At 30-day retention that request returned ~30k docs and 54 MB of JSON on every scheduler CronJob run, enough to OOM-kill the scheduler in production (2026-10-29). Peak RSS is now ~60 MB against production data; deletion rules are unchanged.

---

## [v0.10.0] — 2026-10-27

### Scheduler bounded feed-fetch pool and configurable resources (#246)
`_process_feeds` in `tasks/scheduler.py` previously spawned one unbounded thread per feed simultaneously, buffering every feed body in memory at once and causing periodic `OOMKilled` (exit code 137) restarts of the `scheduler` CronJob at 512Mi. Feed fetching now runs through a bounded `ThreadPoolExecutor` (`SCHEDULER_MAX_WORKERS`, default 4, Helm `scheduler.maxWorkers`), `FetchFeedTask` sends conditional `If-None-Match` / `If-Modified-Since` headers when `etag` / `last_modified` are stored on the feed document and skips unchanged `304 Not Modified` feeds, and `scheduler-cronjob.yaml` reads `scheduler.resources` from Helm values (raised to `1Gi` limit in `values-release.yaml`, matching the worker).

### Model catalog editable in the admin UI
Changing which model serves a purpose needed a Helm values change and an upgrade. Admins now edit the catalog on Settings → System Settings → Model Catalog: models (provider, model, endpoint, API key variable, languages, capabilities) and an ordered model list per purpose. The catalog is stored in `config/llm_catalog` and replaces the Helm one while it exists; "Reset to Helm values" deletes it. Every service re-reads it within 30 seconds and keeps the last known catalog if CouchDB is unreachable. `PUT /api/llm/catalog` validates the whole catalog (`LlmCatalogUpdateRequest`): known providers and capabilities, an endpoint for Ollama, purposes only naming entries with the capability they need, and API key variables restricted to `*_API_KEY` names so an edit cannot hand another secret to a provider.

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
