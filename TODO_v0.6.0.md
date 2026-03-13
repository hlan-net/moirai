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

### 6) Add Dashboard Issue-Raising Wizard
- [x] Add a guided "Raise Issue" wizard in the dashboard article context chat flow.
- [x] Prioritize speed: minimal required fields first, optional refinement after issue creation.
- [x] Bias toward generic issue framing by default (avoid over-specific one-article wording).
- [x] Keep final result resumable in `/chat` as the same contextual session.

### 7) Improve Chat Reliability and Observability
- [x] Show per-response timing in dashboard chat and `/chat`.
- [x] Surface actionable provider-specific errors for nested TaskGroup failures (for example, Ollama endpoint reachability).
- [x] Tune API reverse-proxy timeout behavior for longer chat/tool-assisted requests.

## Next Iteration Candidates

### A) Add Direct Issue-Creation Fast Path
- [ ] Add a dedicated API path for article-to-issue creation to avoid long agent loops for common raise flows.
- [ ] Keep wizard-driven clarification UX, but execute final creation via a deterministic backend path.

### B) Harden LLM Endpoint Diagnostics
- [ ] Add a lightweight settings test for Ollama/OpenAI/Gemini endpoint reachability and DNS failure hints.
- [ ] Show clear in-UI status before sending long chat requests.
