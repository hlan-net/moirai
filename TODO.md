# Moirai TODO

## In Progress / Next

### Cleanup: Retire `events` and `trends` databases
The `issues` DB is now the canonical store (Fates V2). The old `events` and `trends` databases are still being created in `tasks/init.py` but are no longer used as primary storage.
- [x] Remove `events` and `trends` from the `allowed_dbs` list in `tasks/init.py`.
- [x] Verify no active code paths write to them directly (legacy aliases in `mcp_service/tools/issues.py` already redirect to `issues`).

---

## Backend

### CouchDB `validate_doc_update` — Database-Level Validation
Intended to enforce schema at the database level. Previously marked done but **not implemented**.
- [x] Write `validate_doc_update` JavaScript functions for `articles` and `feeds` (required fields, ISO dates, 2-char language codes).
- [x] Push these functions as part of design documents via `tasks/init.py`.
- [x] Test that malformed documents are rejected at the DB level.

### Automated Tests for CouchDB Design Documents
- [x] Implement unit/integration tests for `validate_doc_update` and MapReduce views. Options: test harness with mocked CouchDB responses, or a temporary CouchDB instance in CI.

---

## Frontend (UI)

### Chat Model Selector Persistence
- [x] Persist chat header provider/model changes to server-side user settings (not just localStorage).

### Lifespan View (Fates V2)
A new UI view to visualise the "frequency" of the current userspace — how the stream of articles crystallises into active Issues ("Things that ARE") and sealed Issues ("Things that WERE").
- [x] Add a `LifespanView` Vue component.
- [x] Add a `/lifespan` route to `ui/src/router.ts`.
- [x] Design: show active issues by longevity (transient / temporal / epic) and a historical record of eternal issues.

### River of News Stream Improvements
Three proposals for the Aggregated Stream view, prioritised by complexity:

#### Proposal 1: The "Pure River" (High-Density List)
High information density, mimicking `river.hlan.net`.
- [x] Remove card borders and background colors; use thin separator lines.
- [x] Group articles by feed only when sequential in the timeline.
- [x] Prepend new articles without shifting the current reading position.
- [x] Show a "New Articles Available" toast that scrolls to top on click.

#### Proposal 2: The "Time-Blocked" River
Group by temporal windows instead of sources.
- [x] Section headers: "Last Hour", "Earlier Today", "Yesterday".
- [x] Collapsed summaries by default; expand on click/hover.
- [x] Source favicon and name as a small inline tag next to the title.
- [x] Once a time block is rendered its order is frozen.

#### Proposal 3: The "AI-Annotated" River
Chronological list with AI-driven speed-reading markers.
- [x] Color-coded dots/badges per article indicating Topic, Priority, or Sentiment.
- [x] Items stay at their original position once fetched.
- [x] Depends on an AI annotation enrichment step in the backend.

### Backend AI Annotation Pipeline
Automatic LLM-powered annotation of articles with topics, priority, and sentiment.
- [x] Core annotator module (`tasks/annotator.py`): LLM prompt, validation, CouchDB storage.
- [x] Annotation worker (`tasks/annotation_worker.py`): CouchDB changes-feed listener on `articles` DB.
- [x] Wire annotation worker into `run_worker.py` alongside enrichment worker.
- [x] MCP annotation tools (`mcp_service/tools/annotations.py`): reannotate, list unannotated, stats.
- [x] RSS output: annotation data as `<category>` tags (domain=topic/priority/sentiment) in `api/rss_ops.py`.
- [x] Unit tests (`tests/test_annotator_unit.py`): validation, LLM mocking, store logic, RSS output.
