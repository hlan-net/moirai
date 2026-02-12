# Moirai Architectural Improvements TODO

## Priority 1: CouchDB Aggregations (MapReduce)
- [ ] Create design documents for article counts by language.
- [ ] Implement views for feed health statistics (success/error ratios).
- [ ] Update API to query views instead of performing in-memory aggregations.
- **Branch:** `feature/couchdb-mapreduce-stats`

## Priority 2: Asynchronous Processing Pipeline
- [ ] Refactor `FetchFeedTask` to be a "Raw Collector" (fetches and stores only).
- [ ] Implement a `changes_listener` service to monitor CouchDB `_changes`.
- [ ] Move language detection and metadata extraction to the asynchronous listener.
- **Branch:** `feature/async-enrichment-worker`

## Priority 3: Database-Level Validation
- [ ] Write `validate_doc_update` JavaScript functions for `articles` and `feeds`.
- [ ] Enforce required fields and data types (ISO dates, 2-char language codes).
- [ ] Test rejection of malformed agent tool calls at the DB level.
- **Branch:** `feature/db-schema-validation`
