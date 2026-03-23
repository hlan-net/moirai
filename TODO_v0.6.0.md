# TODO for v0.6.0 Follow-up

**Status: COMPLETE — all items done by v0.6.4**

---

## Completed in v0.6.0

### 1) Centralize and Validate Agent Logic Module Allowlist
- [x] Define one shared allowlist constant for agent logic modules.
- [x] Reuse that constant in API validation, orchestrator execution, and UI selectors.
- [x] Reject non-allowlisted `logic_module` values at request validation time.

### 2) Strengthen Schedule Validation Rules
- [x] Enforce cross-field rules.
- [x] Validate interval format before persistence.
- [x] Return explicit validation messages for invalid interval/unit combinations.

### 3) Add Conflict-Safe CouchDB Write Handling
- [x] Introduce a helper for optimistic concurrency updates with `_rev` refresh/retry.
- [x] Apply it to high-churn write paths.
- [x] Add tests for 409 conflict handling behavior.

### 4) Expand API Route Tests for Agents
- [x] Add route-level tests for `/api/agents` CRUD.
- [x] Cover auth, userspace UUID validation, ownership checks, and admin override behavior.

## Completed by v0.6.4

### 5) Reduce Polling in Agent Orchestrator
- [x] `on_new_article` triggering via CouchDB `_changes` longpoll _(commit f330c08)_
- [x] Scheduled-agent scanning kept as periodic fallback.
- [ ] Telemetry for dispatch lag _(deferred to v0.7.0+)_

### 6) Dashboard Issue-Raising Wizard
- [x] Guided "Raise Issue" wizard in article context chat.
- [x] Direct issue-creation fast path: `POST /api/issues` + single-turn LLM draft _(v0.6.4)_
- [x] LLM no longer asks user for userspace GUID _(v0.6.4)_

### 7) Chat Reliability and Observability
- [x] Per-response timing shown in dashboard and `/chat`.
- [x] Centralized Pinia settings store — settings propagate without reload _(v0.6.4)_
- [x] Dashboard columns synchronized to 30s polling _(v0.6.4)_

### 8) LLM Endpoint Diagnostics
- [ ] Lightweight reachability test in Settings _(deferred to v0.7.0)_

---

See `TODO_v0.7.0_ROADMAP.md` for next iteration.
