# Moirai 0.7.1 Agentic Improvements TODO

## Overview

This release focuses on improving the agentic capabilities of Moirai, making agents more autonomous, reliable, context-aware, and observable.

---

## 1) MCP Tool Contract Hardening (Effort: M) [P0]

**Problem:** Current MCP tools return inconsistent strings/dicts with no structured error handling.

**Scope:**
- Standardize all MCP responses with: `status`, `data`, `error_code`, `message`, `retryable`, `next_action`, `correlation_id`.
- Define canonical error codes (e.g., `VALIDATION_ERROR`, `TRANSIENT_NETWORK`, `CONFLICT_REVISION`).
- Add retry guidance metadata for transient failures (`retry_after_ms`, `max_retries_hint`).

**Acceptance criteria:**
- 100% of MCP tools return the standardized response envelope.
- Agent runtime branches on `retryable` and `next_action` without string parsing.
- Tests cover success, transient failure, and non-retryable failure for critical tool groups.

---

## 2) Agent Observability + Safe Intervention Controls (Effort: S/M) [P0]

**Problem:** Limited visibility into agent runs; no way to pause risky operations.

**Scope:**
- Capture traces for plan steps, tool calls, latency, retries, error classes, and final outcome.
- Add risk flags for destructive or irreversible actions and require human approval when configured.
- Expose `correlation_id`-linked run timelines via structured logs or operator view.

**Acceptance criteria:**
- Every run emits an end-to-end trace with step and tool-level metrics.
- Risky operations can be paused/approved/denied via configuration.
- Staging drills show improved mean time to resolution due to trace visibility.

---

## 3) Context Window Management + Summarization (Effort: S/M) [P1]

**Problem:** Chat history is capped at 6 messages (`CHAT_HISTORY_LIMIT`). Older context is dropped, causing agents to "forget" mid-conversation.

**Scope:**
- Add progressive summarization of older messages before truncation.
- Inject summary as a "memory preamble" in system message.
- Allow configurable context window per userspace or agent config.

**Acceptance criteria:**
- Long conversations maintain coherence beyond 6 turns.
- Summary quality validated via manual review of edge cases.
- No regression in response latency (summarization can be async/cached).

---

## 4) Plan -> Execute -> Reflect Runtime Loop (Effort: M) [P1]

**Problem:** Current agent loop is reactive with no recovery or replan on failure.

**Scope:**
- Add explicit internal phases for planning, execution, and reflection/replan.
- Reflection evaluates failures using tool metadata and chooses next-best action.
- Enforce max-iteration and timeout guardrails to avoid runaway loops.

**Acceptance criteria:**
- Multi-step benchmark tasks (3+ dependent steps) show improved completion rate vs baseline.
- Agent performs at least one valid automatic replan on recoverable failures.
- Loop termination is deterministic under iteration/timeout limits.

---

## 5) Agent Self-Evaluation + Confidence Scoring (Effort: S/M) [P2]

**Problem:** Agents return results without indicating confidence or flagging uncertainty.

**Scope:**
- Add a final self-evaluation pass after task completion.
- Output confidence score (0-1) and uncertainty flags (`low_data`, `ambiguous_intent`, `tool_failure_recovered`).
- Surface confidence in API response and UI.

**Acceptance criteria:**
- Every agent response includes a confidence score.
- Low-confidence responses are flagged in UI (e.g., warning indicator).
- Calibration: confidence correlates with actual success rate in test scenarios.

---

## 6) Per-Userspace Agent Memory (Effort: M/L) [P1]

**Problem:** No memory persistence across sessions; agents re-learn context every run.

**Scope:**
- Add short-term memory by userspace + session (recent tool outcomes, partial plans, unresolved items).
- Add lightweight long-term memory by userspace (preferences, recurring entities, successful strategies).
- Add TTL, size limits, and pruning/summarization policy.
- Build on existing `SessionLogger` infrastructure.

**Acceptance criteria:**
- Follow-up requests in the same userspace reuse prior context without re-prompting known preferences.
- Retrieval quality targets are met for seeded memory scenarios.
- Isolation tests verify zero cross-userspace leakage.

---

## 7) Tool Dependency Graph + Parallel Execution (Effort: M) [P2]

**Problem:** Current agent loop executes tools sequentially with no awareness of parallelization opportunities.

**Scope:**
- Define tool dependency metadata (e.g., `search_articles` before `forge_issue`).
- Planner emits a DAG of tool calls when multiple are needed.
- Executor runs independent branches in parallel (asyncio).

**Acceptance criteria:**
- Multi-tool workflows show measurable latency improvement (target: 30%+ on 3+ tool chains).
- Dependency violations are caught at plan time, not runtime.
- Parallel execution is safe (no race conditions on shared state).

---

## Suggested Delivery Order for 0.7.1

| Order | Improvement | Effort | Priority | Rationale |
|-------|-------------|--------|----------|-----------|
| 1 | MCP Tool Contract Hardening | M | P0 | Foundation for all other improvements |
| 2 | Observability + Intervention Controls | S/M | P0 | Visibility before adding complexity |
| 3 | Context Window Management + Summarization | S/M | P1 | Quick win, improves UX immediately |
| 4 | Plan/Execute/Reflect Loop | M | P1 | Core agentic capability |
| 5 | Agent Self-Evaluation + Confidence Scoring | S/M | P2 | Builds on reflection loop |
| 6 | Per-Userspace Agent Memory | M/L | P1 | Extends SessionLogger foundation |
| 7 | Tool Dependency Graph + Parallel Execution | M | P2 | Performance optimization layer |

---

## Notes

- Items 1-4 are recommended for initial 0.7.1 scope
- Items 5-7 can be deferred to 0.7.2 if timeline is tight
- All improvements should maintain strict userspace isolation
