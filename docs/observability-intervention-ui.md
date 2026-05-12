# Observability & Intervention UI

## Overview
Moirai's `AgentOrchestrator` dispatches scheduled and event-driven agents on behalf of the human in a userspace. As soon as agents act autonomously — annotating articles, raising issues, deleting stale entities, posting to social — a human needs two things they did not need when the platform was purely passive: **visibility** into what the agent did, and **control** when something looks wrong.

v0.8.0 delivered the *backend* of this capability: per-step tracing, an approval gate on destructive tool calls, mid-flight cancellation, and a session timeline API. This document describes the *dashboard surfaces* that consume that backend and bring it within reach of the human running the userspace.

## Conceptual Framework

### Sessions as the unit of agent activity
Every agent run, chat turn, or `on_new_article` dispatch is a **session**. A session has a single owning userspace, a type (`scheduled_agent`, `on_new_article`, `chat`), a status that progresses from `running` to one of `success` / `error` / `cancelled`, and an ordered list of steps (LLM calls and MCP tool calls). The session is the natural unit a human reasons about: "what did this agent do at 14:00?"

Sessions are intentionally **ephemeral** — Redis-backed with a 7-day TTL. They are debugging and intervention surfaces, not a permanent audit log. Persistence (compliance, long-term analytics) is an explicitly deferred concern. The platform's persistent record of meaning lives in Issues, not in agent run history.

### Approvals as a guardrail, not a gate
The approval mechanism wraps a hardcoded list of destructive tools (`delete_*`, `publish_to_bluesky`, `delete_user`). An agent configured with `require_approval: true` pauses before invoking any of them; a pending request appears in the human's inbox and the agent blocks (up to a timeout) on the human's decision.

The intent is **selective human review of irreversible actions**, not a general workflow approval system. Non-destructive tool calls are not gated — agents are trusted to read, annotate, and create freely within their userspace.

### Cancellation as a circuit breaker
A running session can be cancelled mid-flight. The mechanism is cooperative: the next tool call boundary checks for a Redis cancel flag and raises an `AgentCancelledException` that the session context manager catches and records. There is no in-flight LLM-call kill — a single ongoing LLM request will complete before cancellation takes effect.

This is sufficient for the realistic failure mode it addresses: an agent stuck in a long retry loop, or one mid-way through a slow batch.

## Functional Components

### Sessions List — `/sessions`
A first-class navigation destination, sibling to Stream and Agents. Lists recent sessions for the active userspace with timestamp, agent name, type, status, duration, and step count. Default ordering is most-recent-first; pagination uses the existing `limit`/`offset` query parameters. A row links into the Session Detail view.

The list is the operator's habitual surface — the place to glance at "is the platform doing what I expect?" without diving into any individual run.

### Session Detail — `/sessions/:id`
A single session rendered as a structured timeline of its steps. Each step shows:

- **Type:** LLM call, tool call, or approval gate.
- **Subject:** model + provider for LLM calls; tool name for tool calls.
- **Status:** success, error, retried, cancelled, pending-approval, timeout.
- **Latency:** measured server-side, in milliseconds.
- **Input / output summaries:** truncated to 500 characters at the source so the wire payload stays small.
- **Risk level & attempt number** for tool calls.

When the session is still `running`, the page exposes a **Cancel** action that posts to `/api/sessions/<id>/cancel`. Status flips to `cancelled` at the next tool-call boundary.

The visual rendering borrows from the existing chat message list pattern — agents and chat sessions are kinds of the same thing (a sequence of LLM calls and tool calls), and the operator should not have to learn two timelines.

### Approvals Inbox — `/approvals`
Pending approval requests across the user's userspaces, with a count badge on the nav link so the inbox surfaces itself. Each entry shows the agent, the tool being requested, an args summary, and **Approve** / **Deny** buttons.

The page polls at ~10s intervals. Decisions write to Redis, where the blocked agent picks them up at its next polling boundary; an approved agent proceeds with the tool call, a denied agent returns a structured `denied` error and continues its loop (typically with a graceful exit).

The inbox reuses the confirmation-panel UX already proven in `ContextChatModal.vue` for quick-action confirmation — consistent visual language across "do you want me to do this?" moments anywhere in the app.

### Cancellation surface
Cancellation is not a standalone page — it is a button on the Session Detail view, visible only while a session is `running`. This keeps the action grounded in the context of what is being stopped, rather than presented as a separate operational lever.

## Where the surfaces live

```
Top nav: Stream · Mythology · Dashboard · Lifespan · Chat · Sessions · Approvals · Settings · Agents
                                                       ─────────   ──────────
                                                       new          new (with badge)
```

The choice of top-level routes (vs. a Settings tab or a sub-section of `/agents`) reflects that these are **operational surfaces**, not configuration. They are checked routinely, not visited once during setup.

## Out of scope

The following are explicitly **not** part of this work — they are listed here so a reader understands the deliberate edges of the current scope:

- **Approval audit log** persisted beyond Redis TTL. Issue history is the durable record; an "I clicked deny" archive is not.
- **Rejection reasons** captured on Deny. The session log records the decision; nuance lives in the surrounding Issue or in a chat follow-up.
- **Retry of a failed session** from the UI. Re-trigger by re-running the agent, not by replaying its history.
- **Per-step approval** beyond the destructive-tools allowlist. Trust agents within their userspace; gate only the irreversible.
- **External tracing backends** (Jaeger, Tempo) for session data. See [Metrics & Alerting](./metrics-and-alerting.md) for the metrics-side observability story.

## See also
- [Metrics & Alerting](./metrics-and-alerting.md) — the operational observability layer, complementary to this UI.
- [Agentic Improvements](./agentic-improvements.md) — the longer-horizon agent autonomy work that is explicitly deferred.
