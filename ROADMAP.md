# Moirai Project Roadmap

This document outlines the planned improvements and strategic direction for Moirai. For detailed technical designs and conceptual rationale, refer to the individual documents in the [`docs/`](docs/) directory.

---

## 🗺️ Vision

Moirai is, first and foremost, an **aggregated RSS reader** — the Stream page is the product. On top of that reader, the Greek Fates metaphor names an **analytical extension**: Clotho gathers the thread (feeds), Lachesis measures it (issues), Atropos acts on it (agents). The Fates layer helps the human do analysis and follow-ups on what flows through the Stream — it is not a replacement for reading, it is what comes after reading.

Three principles flow from that vision:

1. **Reader-first.** The Stream's quality is non-negotiable; analytical features are additive.
2. **Issue-centric meaning.** Persistence and significance belong to Issues, not to article state. The Stream is a flow, not an inbox.
3. **Visible, controllable agents.** As soon as agents act autonomously, the human needs both visibility into and control over their behavior — that visibility is part of the product, not an afterthought.

---

## ✅ What's shipped

| Version | Highlights |
|---|---|
| **v0.8.1** | Hotfix: worker memory bump (OOMKill), Gemini chat context preamble + copy/download fix. |
| **v0.8.0** | Agent observability backend: step-level tracing, approval gate, cancellation, session timeline API. MCP tools migrated to standardized `MCPResponse` envelope. Wacom pen click-drag fix. |
| **v0.7.2** | Hotfix: Wacom pen drag threshold. |
| **v0.7.1** | Dependency bumps (starlette 1.0, bcrypt 5.0). Public Mythology page; public/private issue distinction. |
| **v0.7.0** | Userspace as a first-class document with LLM credentials. Session logging foundation. Chat LLM override. Quick actions. Draggable chat. Bluesky export. |

The current production deployment is **v0.8.1**.

---

## 🎯 Current priorities

After the v0.8.x agent-observability arc and with the Stream page in good shape, the work order is **"finish what we started, fix the boring stuff, defer the moonshots"**:

1. **Finish observability & intervention** — wire the dashboard to the v0.8.0 backend, ship operational metrics + alerts.
2. **Reader polish** — opportunistic, small. No headline work; only when real friction emerges.
3. **Foundation** — security hardening and deployment UX. Overdue.
4. **Agentic autonomy (deferred)** — Plan-Execute-Reflect, persistent agent memory. Last.

---

## 🚀 Next release: v0.9.0 — Visible Agents

**Focus:** Make the v0.8.0 agent observability/intervention work usable by the human in the loop, and surface platform health to the operator.

### Track 1 — Observability & Intervention UI
See [`docs/observability-intervention-ui.md`](docs/observability-intervention-ui.md) for full conceptual treatment.

- **Sessions list** (`/sessions`) — first-class navigation destination listing recent agent and chat sessions for the active userspace.
- **Session detail** (`/sessions/:id`) — timeline of steps (LLM calls, tool calls, approval gates) for a single run, with a Cancel action while running.
- **Approvals inbox** (`/approvals`) — pending approval requests across the user's userspaces, with a count badge on the nav link. Approve / Deny posts to the existing backend.

No backend changes — every endpoint is already in place from v0.8.0.

### Track 2 — Metrics & Alerting
See [`docs/metrics-and-alerting.md`](docs/metrics-and-alerting.md) for full conceptual treatment.

- **Moirai-specific Prometheus metrics** — `moirai_articles_ingested_total`, `moirai_articles_per_issue_total`, `moirai_agent_sessions_*`, `moirai_agent_tool_call_latency_seconds`, `moirai_approvals_*`. Labels include `feed_id`, `issue_id`, `agent_id`, `userspace`.
- **ServiceMonitor coverage** — extend Helm so the API (and worker, if instrumented there) are scraped alongside the existing MCP-server monitor.
- **PrometheusRule alerts** — `MoiraiPodOOMKilled`, `MoiraiLowIngestRate`, `MoiraiAgentErrorRate`, `MoiraiApprovalsBacklog`. The v0.8.1 OOM incident is the motivating example.
- **Grafana dashboard** — committed JSON, auto-imported via the standard ConfigMap pattern. Panels for ingestion velocity, agent activity, tool latencies, approval queue, pod health.
- **Operator guide** — recipes for common questions, dashboard import instructions, alert meanings.

---

## 🛠️ Future Releases

### v0.10.0 (tentative): Foundation Hardening
**Focus:** Security and deployment ergonomics. Not glamorous, overdue.

- **[Security Hardening](docs/security-enhancements.md):** JWT session model, Role-Based Access Control (RBAC), server-side userspace isolation.
- **[Deployment UX](docs/deploy-ux-improvements.md):** Reduce the operator overhead of running Moirai in varied environments.

### v1.0.0 (deferred): Agent Autonomy
**Focus:** The speculative agentic bets — explicitly last in the priority order.

- **[Agentic Infrastructure](docs/agentic-improvements.md):** Plan-Execute-Reflect loops, persistent agent memory.

---

## 🛡️ Strategic Pillars (cross-cutting)

These are not version-pinned; they accumulate as the platform grows.

### Reader Experience
The Stream page is the product's primary surface. It is **explicitly not** a database to be queried (no in-stream search/filter, no keyboard navigation) and **explicitly not** an inbox (no read/unread, no save/archive). Improvements should sharpen the flow itself: feed health, deduplication, image rendering, mobile layout, density.

### Input Diversity & Precision
- **[Pointer Interaction Support](docs/pointer-interaction-wacom-touch.md):** Continued work on Wacom, touch, and mouse parity across the interactive dashboard.

### Architectural Foundations
- **MCP Tool Standardization** — shipped in v0.8.0 (standardized `MCPResponse` envelope across all tools).
- **[Configuration Management](docs/settings-store-refactoring.md):** Centralized settings.

### Wizard & Capture
- **[Form-Based Issue Wizard](docs/proposal-form-wizard.md):** Traditional UI alternative for structured issue creation.
- **[Issue Raise Wizard Refinement](docs/issue-raise-wizard.md):** Continued tuning of the LLM-driven path.

### Social
- **[Social Export (Bluesky)](docs/social-export-bluesky.md):** Shipped in v0.7.0; reframed as "share something from the reader / from an issue," not "publish agent output."

---

## 📚 Reference Documentation

- **[Architecture Overview](docs/architecture.md):** The high-level system design.
- **[Observability & Intervention UI](docs/observability-intervention-ui.md):** Sessions, approvals, cancellation — the dashboard surfaces for agent activity.
- **[Metrics & Alerting](docs/metrics-and-alerting.md):** Prometheus instrumentation, alerts, and Grafana dashboards.
- **[External API Guide](docs/external-api.md):** How to integrate with Moirai from outside.
- **[Tutorials](docs/readme.md):** User, Admin, and Developer guides.
- **[Releasing Process](docs/releasing.md):** Standard procedure for project releases.
