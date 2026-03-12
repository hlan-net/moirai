# TODO for v0.6.0 Follow-up

This file tracks follow-up work after the v0.6.0 release.

## Completed in v0.6.0

### 1) Centralize and Validate Agent Logic Module Allowlist
- [x] Define one shared allowlist constant for agent logic modules.
- [x] Reuse that constant in API validation, orchestrator execution, and UI selectors.
- [x] Reject non-allowlisted `logic_module` values at request validation time.

### 2) Strengthen Schedule Validation Rules
- [x] Enforce cross-field rules:
  - `trigger_type=scheduled` requires `schedule_interval`.
  - `trigger_type=on_new_article` disallows `schedule_interval`.
- [x] Validate interval format before persistence.
- [x] Return explicit validation messages for invalid interval/unit combinations.

### 3) Add Conflict-Safe CouchDB Write Handling
- [x] Introduce a helper for optimistic concurrency updates with `_rev` refresh/retry.
- [x] Apply it to high-churn write paths (agent status and `last_run_at` updates).
- [x] Add tests for 409 conflict handling behavior.

### 4) Expand API Route Tests for Agents
- [x] Add route-level tests for `/api/agents` CRUD.
- [x] Cover auth, userspace UUID validation, ownership checks, and admin override behavior.
- [x] Cover cross-userspace access denial behavior and payload sanitization/validation paths.

## Remaining Follow-up

### 5) Reduce Polling in Agent Orchestrator
- [ ] Move `on_new_article` triggering toward CouchDB `_changes`-driven dispatch.
- [ ] Keep scheduled-agent scanning as a periodic fallback.
- [ ] Add telemetry for dispatch lag and processing outcomes.
