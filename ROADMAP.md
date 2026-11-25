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
| **v0.12.0** | The UI is the Stream page, Login and Settings (#375): the Dashboard, Lifespan, Chat, Agents, Sessions and Mythology views are removed from the frontend, their backend stays. Feed management moves to a Feeds tab in Settings. |
| **v0.11.x** | Stream sections: Top stories, Sports, Culture, Business, several at once from one menu. Stream page served from the `stream.rss` cache. Python 3.12. MCP Python SDK 2.x; agents can call tools. Pooled CouchDB connections; bounded whole-database reads. Formatting enforced in CI; Python pins visible to Dependabot. |
| **v0.10.x** | Single implicit userspace (MCP, REST API, UI). Model catalog for annotation, chat, agents and social export, editable in the admin UI. Bounded feed-fetch pool. Security and dependency updates. |
| **v0.9.x** | AISA in-cluster inference proxy as an LLM provider. Closed annotation topic vocabulary and re-annotation at backlog scale. Scheduler and worker split from the API. Issues model ("The Fates", 2nd iteration). |
| **v0.8.1** | Hotfix: worker memory bump (OOMKill), Gemini chat context preamble + copy/download fix. |
| **v0.8.0** | Agent observability backend: step-level tracing, approval gate, cancellation, session timeline API. MCP tools migrated to standardized `MCPResponse` envelope. Wacom pen click-drag fix. |
| **v0.7.2** | Hotfix: Wacom pen drag threshold. |
| **v0.7.1** | Dependency bumps (starlette 1.0, bcrypt 5.0). Public Mythology page; public/private issue distinction. |
| **v0.7.0** | Userspace as a first-class document with LLM credentials. Session logging foundation. Chat LLM override. Quick actions. Draggable chat. Bluesky export. |

See [`CHANGELOG.md`](CHANGELOG.md) for the latest release and the full history.

---

## 🎯 Current priorities

Since v0.12.0 the UI is the Stream page, Login and Settings (#375). The views that were removed keep their backend, and their functions return selectively as parts of the Stream page. The work order is **"bring functions back to the Stream, finish what we started, fix the boring stuff, defer the moonshots"**:

1. **The Stream as the whole UI** — return the functions of the removed views as parts of the Stream page (#376 to #379).
2. **Finish observability & intervention** — give the v0.8.0 backend a place in the reduced UI, ship operational metrics + alerts.
3. **Foundation** — security hardening and deployment UX. Overdue.
4. **Agentic autonomy (deferred)** — Plan-Execute-Reflect, persistent agent memory. Last.

---

## 🚀 Next up: The Stream as the whole UI

**Focus:** What the removed views did comes back where the reader already is, one function at a time, each when it has a place on the Stream page.

| Issue | What | Status |
|---|---|---|
| #376 | **Side column** for a conversation about an article, or for an event or a trend, beside the stream | Merged, unreleased |
| #377 | **Search** from the Stream page, for a logged-in reader | In review (PR #385) |
| #378 | **One row for a story covered by several sources** | Open |
| #379 | **Share an article to Bluesky**, with the post text reviewed before sending | Open |
| #309 | **Convergence feed**: an RSS output of subjects several sources pick up, alongside `stream.rss` | Idea, not scheduled |

#378 and #309 need the same answer to "are these two articles the same story"; whatever decides it should serve both.

---

## 🔭 After that: Visible Agents

> This was planned as v0.9.0. The v0.9–v0.12 releases shipped other work (see "What's shipped"), so it is not yet assigned to a version.

**Focus:** Make the v0.8.0 agent observability/intervention work usable by the human in the loop, and surface platform health to the operator.

### Track 1 — Observability & Intervention UI
See [`docs/observability-intervention-ui.md`](docs/observability-intervention-ui.md) for the conceptual treatment. That document describes separate `/sessions` and `/approvals` pages. A Sessions list and session detail shipped in v0.8.2 and were removed with the other views in #375, so the shape below has to be decided again as parts of the Stream page or Settings before it is built.

- **Sessions list** — recent agent and chat sessions for the active userspace.
- **Session detail** — timeline of steps (LLM calls, tool calls, approval gates) for a single run, with a Cancel action while running.
- **Approvals inbox** — pending approval requests with a count badge. Approve / Deny posts to the existing backend.

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

### Foundation Hardening (unscheduled; originally pencilled in as v0.10.0)
**Focus:** Security and deployment ergonomics. Not glamorous, overdue.

- **[Security Hardening](docs/security-enhancements.md):** JWT session model, Role-Based Access Control (RBAC), server-side userspace isolation.
- **[Deployment UX](docs/deploy-ux-improvements.md):** Reduce the operator overhead of running Moirai in varied environments.

### v1.0.0 (deferred): Agent Autonomy
**Focus:** The speculative agentic bets — explicitly last in the priority order.

- **[Agentic Infrastructure](docs/agentic-improvements.md):** Plan-Execute-Reflect loops, persistent agent memory.

### Kubernetes-native Inference (capability-gated)
**Focus:** Represent the LLM backends (Ollama, hailo-ollama on `192.168.1.12`) as Kubernetes resources instead of raw URLs in Helm values.
**Priority:** Low. Decided 2026-09-28: revisit each item when the cluster in use gains the listed capability. As of that date (k3s v1.36.4) it has Gateway API base CRDs only.

| Item | Capability gate |
|------|-----------------|
| **[External Ollama as a Service](docs/k8s-external-ollama-service.md)**: selectorless Service + EndpointSlice | None; possible today |
| **[Gateway API Inference Extension](docs/k8s-gateway-inference-extension.md)**: `InferencePool` routing | Inference Extension CRDs + in-cluster model-server pods |
| **[In-cluster Ollama](docs/k8s-in-cluster-ollama.md)**: KServe / KubeAI / ollama-operator | Operator installed + node capacity for models |
| **[DRA for the Hailo NPU](docs/k8s-dra-hailo-npu.md)**: NPU as a schedulable resource | NPU host joined as node + Hailo DRA driver/device plugin |

---

## 🛡️ Strategic Pillars (cross-cutting)

These are not version-pinned; they accumulate as the platform grows.

### Reader Experience
The Stream page is the product's primary surface, and since v0.12.0 the only reading UI. It is **explicitly not** an inbox (no read/unread, no save/archive). The earlier rule that it is not a database to be queried has been relaxed: the section menu (#344) chooses what flows, and search (#377) lets a logged-in reader find an article, with the stream kept loaded underneath. Keyboard shortcuts for moving through the stream remain out of scope. Improvements should sharpen the flow itself: feed health, deduplication (#378), image rendering, mobile layout, density.

- **[Stream Sections](docs/stream-sections.md):** Four newspaper-style tabs — Top stories (default), Sports, Culture, Business. A fixed editorial split of the flow, assigned at ingestion from feed category and link path (annotation topic as fallback), not a reader-composed filter. Shipped in v0.11.x (#266); since v0.11.5 several sections can be chosen at once from one menu (#344). The closed topic vocabulary (#249) serves the fallback.

### Input Diversity & Precision
- **[Pointer Interaction Support](docs/pointer-interaction-wacom-touch.md):** Wacom, touch, and mouse parity. Written for the Dashboard, which #375 removed; it now applies to the Stream page and its side column.

### Architectural Foundations
- **MCP Tool Standardization** — shipped in v0.8.0 (standardized `MCPResponse` envelope across all tools).
- **[Configuration Management](docs/settings-store-refactoring.md):** Centralized settings.

### Wizard & Capture
Issue creation had its UI in the views #375 removed; the backend remains. Both items wait for a place on the Stream page (the side column, #376, is the likely one).

- **[Form-Based Issue Wizard](docs/proposal-form-wizard.md):** Traditional UI alternative for structured issue creation.
- **[Issue Raise Wizard Refinement](docs/issue-raise-wizard.md):** Continued tuning of the LLM-driven path.

### Social
- **[Social Export (Bluesky)](docs/social-export-bluesky.md):** Shipped in v0.7.0 for issues; reframed as "share something from the reader / from an issue," not "publish agent output." The issue share lost its UI in #375; sharing an article from the Stream page is #379.

---

## 📚 Reference Documentation

- **[Architecture Overview](docs/architecture.md):** The high-level system design.
- **[Observability & Intervention UI](docs/observability-intervention-ui.md):** Sessions, approvals, cancellation — the dashboard surfaces for agent activity.
- **[Metrics & Alerting](docs/metrics-and-alerting.md):** Prometheus instrumentation, alerts, and Grafana dashboards.
- **[External API Guide](docs/external-api.md):** How to integrate with Moirai from outside.
- **[Tutorials](docs/readme.md):** User, Admin, and Developer guides.
- **[Releasing Process](docs/releasing.md):** Standard procedure for project releases.
