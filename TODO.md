# Moirai TODO

## In Progress / Next

### Cleanup: Retire `events` and `trends` databases
The `issues` DB is now the canonical store (Fates V2). The old `events` and `trends` databases are still being created in `tasks/init.py` but are no longer used as primary storage.
- [ ] Remove `events` and `trends` from the `allowed_dbs` list in `tasks/init.py`.
- [ ] Verify no active code paths write to them directly (legacy aliases in `mcp_service/tools/issues.py` already redirect to `issues`).

---

## Backend

### CouchDB `validate_doc_update` — Database-Level Validation
Intended to enforce schema at the database level. Previously marked done but **not implemented**.
- [ ] Write `validate_doc_update` JavaScript functions for `articles` and `feeds` (required fields, ISO dates, 2-char language codes).
- [ ] Push these functions as part of design documents via `tasks/init.py`.
- [ ] Test that malformed documents are rejected at the DB level.

### Automated Tests for CouchDB Design Documents
- [ ] Implement unit/integration tests for `validate_doc_update` and MapReduce views. Options: test harness with mocked CouchDB responses, or a temporary CouchDB instance in CI.

---

## Frontend (UI)

### Lifespan View (Fates V2)
A new UI view to visualise the "frequency" of the current userspace — how the stream of articles crystallises into active Issues ("Things that ARE") and sealed Issues ("Things that WERE").
- [ ] Add a `LifespanView` Vue component.
- [ ] Add a `/lifespan` route to `ui/src/router.ts`.
- [ ] Design: show active issues by longevity (transient / temporal / epic) and a historical record of eternal issues.

### River of News Stream Improvements
Three proposals for the Aggregated Stream view, prioritised by complexity:

#### Proposal 1: The "Pure River" (High-Density List)
High information density, mimicking `river.hlan.net`.
- [ ] Remove card borders and background colors; use thin separator lines.
- [ ] Group articles by feed only when sequential in the timeline.
- [ ] Prepend new articles without shifting the current reading position.
- [ ] Show a "New Articles Available" toast that scrolls to top on click.

#### Proposal 2: The "Time-Blocked" River
Group by temporal windows instead of sources.
- [ ] Section headers: "Last Hour", "Earlier Today", "Yesterday".
- [ ] Collapsed summaries by default; expand on click/hover.
- [ ] Source favicon and name as a small inline tag next to the title.
- [ ] Once a time block is rendered its order is frozen.

#### Proposal 3: The "AI-Annotated" River
Chronological list with AI-driven speed-reading markers.
- [ ] Color-coded dots/badges per article indicating Topic, Priority, or Sentiment.
- [ ] Items stay at their original position once fetched.
- [ ] Depends on an AI annotation enrichment step in the backend.
