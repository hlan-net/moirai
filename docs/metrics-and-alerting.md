# Metrics & Alerting

## Overview
Moirai exposes Prometheus metrics from its MCP server (port 9000) and from its Flask API (`PrometheusMetrics` middleware on the API port). The deployed cluster runs the standard `kube-prometheus-stack` (Prometheus + Alertmanager + Grafana + operator), and a `ServiceMonitor` already scrapes the MCP server's metrics endpoint.

What is missing from production today is the **Moirai-specific signal layer**: domain-meaningful counters and histograms for ingestion, agent activity, and approvals; a Grafana dashboard that gives the operator a single view of platform health; and PrometheusRule alerts that page the operator before things go wrong (e.g., the v0.8.1 worker OOMKill that ran undetected for hours).

This document defines that signal layer and the operator-facing surfaces around it.

## Conceptual Framework

### Two complementary observability layers
Moirai uses two distinct observability layers, intentionally separate:

| Layer | Audience | Granularity | Retention | Surface |
|---|---|---|---|---|
| **Sessions / approvals** (see [Observability & Intervention UI](./observability-intervention-ui.md)) | Operator using the dashboard | Per agent run, per step | 7 days (Redis) | `/sessions`, `/approvals` |
| **Metrics & alerts** (this doc) | Operator with kubectl/Grafana access | Aggregate (counters, histograms) | Months (Prometheus) | Grafana + Alertmanager |

The session UI answers "what did this specific run do?" The metrics layer answers "what is the platform doing in aggregate, and is anything trending toward failure?"

### Domain metrics, not just runtime metrics
Off-the-shelf Flask metrics (request counts, latencies) tell you the API is alive. They do not tell you whether **articles are flowing**, whether **agents are succeeding**, or whether **a feed has gone silent**. Moirai's instrumentation prioritizes domain-level counters labelled by `feed_id`, `issue_id`, `agent_id`, and `userspace` so the operator can ask the questions that actually matter for a press-review platform.

## The Signal Layer

### Domain metrics

| Metric | Type | Labels | Source |
|---|---|---|---|
| `moirai_articles_ingested_total` | Counter | `feed_id`, `userspace` | Article-creation path in the feeds tool. Provides per-feed velocity via `rate()`. |
| `moirai_articles_per_issue_total` | Counter | `issue_id`, `userspace` | Annotation / issue-update path. Provides per-issue engagement. |
| `moirai_agent_sessions_started_total` | Counter | `agent_id`, `type` | `tasks/session_logger.py:start_session` |
| `moirai_agent_session_duration_seconds` | Histogram | `agent_id`, `status` | `tasks/session_logger.py:finish_session` |
| `moirai_agent_sessions_active` | Gauge | — | inc/dec around `session()` context manager |
| `moirai_agent_tool_call_latency_seconds` | Histogram | `tool`, `status` | `tasks/tracing_mcp_client.py:call_tool` |
| `moirai_approvals_pending` | Gauge | `userspace` | Pending queue depth, sampled by metrics callback |
| `moirai_approvals_decided_total` | Counter | `decision` | `tasks/tracing_mcp_client.py` after Redis decision read |

These complement (do not replace) the existing Flask, Python runtime, and kube-state-metrics signals.

### ServiceMonitors
A `ServiceMonitor` for the MCP server (`helm/templates/mcp-server.yaml`) is already deployed and scraping. The API service needs its own ServiceMonitor — its `/metrics` endpoint exists via the Flask `PrometheusMetrics` middleware but is not currently being scraped. If domain metrics fire in the worker container (which doesn't expose an HTTP port today), a metrics sidecar or a dedicated metrics port on the worker is required.

### PrometheusRule alerts

Four alerts cover the realistic failure modes a press-review platform owner cares about:

| Alert | Condition | Why it matters |
|---|---|---|
| `MoiraiPodOOMKilled` | `kube_pod_container_status_last_terminated_reason{namespace, reason="OOMKilled"} > 0` | The v0.8.1 worker incident was hours of silent degradation. This rule would have paged at the first restart. |
| `MoiraiLowIngestRate` | `rate(moirai_articles_ingested_total[1h]) == 0` for > 30m | A platform whose entire purpose is ingesting articles should never be ingesting zero. Catches broken feeds, network partitions, scheduler crashes. |
| `MoiraiAgentErrorRate` | Error-status session ratio > 50% over 1h | Distinguishes a broken agent from a noisy LLM. |
| `MoiraiApprovalsBacklog` | `moirai_approvals_pending > 0` for > 10m | A queued approval the human forgot. Agents stay blocked until the timeout fires. |

Rule thresholds are configurable via `helm/values.yaml` so the operator can tune them per environment.

### Grafana dashboard
A committed dashboard (`helm/dashboards/moirai-overview.json`) auto-loads into Grafana via a ConfigMap labelled `grafana_dashboard: "1"` (the standard sidecar pattern for the Helm-installed Grafana). Panels:

- **Article velocity per feed** — `topk(10, rate(moirai_articles_ingested_total[5m]))`. Reveals which feeds are productive and which have gone silent.
- **Articles per issue** — `topk(10, rate(moirai_articles_per_issue_total[1h]))`. Surfaces hot issues.
- **Active sessions** — `moirai_agent_sessions_active`.
- **Session duration p50/p95** — `histogram_quantile(0.5|0.95, moirai_agent_session_duration_seconds_bucket)`.
- **Tool call latency** — `histogram_quantile(0.95, sum by (tool, le) (rate(moirai_agent_tool_call_latency_seconds_bucket[5m])))`.
- **Approval queue depth** — `sum(moirai_approvals_pending)`.
- **Pod memory & CPU** — standard `container_memory_working_set_bytes` and CPU rates, filtered to `namespace="moirai-release"`.

The dashboard is a starting point. The operator is expected to fork and adapt it for their specific environment.

## Operator Guide

### Verifying scrape targets
```bash
kubectl get servicemonitor -n moirai-release
# Expect: moirai-release-mcp-server, moirai-release-api
```

### Spot-checking metrics
```bash
kubectl port-forward -n moirai-release svc/moirai-release-mcp-server 9000:9000
curl localhost:9000/metrics | grep ^moirai_
```

### Reading the dashboard
```bash
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Open http://localhost:3000 — the "Moirai Overview" dashboard appears in the list.
```

### Sample PromQL recipes

**Which feed has gone silent in the last 6 hours?**
```
moirai_articles_ingested_total - moirai_articles_ingested_total offset 6h == 0
```

**What's my agent failure rate over the last day?**
```
sum(rate(moirai_agent_session_duration_seconds_count{status="error"}[1d]))
  / sum(rate(moirai_agent_session_duration_seconds_count[1d]))
```

**What tool is the slowest at p95?**
```
topk(5, histogram_quantile(0.95,
  sum by (tool, le) (rate(moirai_agent_tool_call_latency_seconds_bucket[1h]))))
```

## Out of scope

- **OTLP trace export** to Jaeger/Tempo. Step-level traces live in Redis under the session log; an external tracing backend is a v1.0 concern, not a v0.8.x one.
- **Persistent session history beyond 7 days.** If you need long-range agent activity analysis, query Prometheus aggregates, not individual session traces.
- **Per-userspace dashboards.** The starter dashboard is platform-wide. Multi-tenant dashboard variants can be derived from it.

## See also
- [Observability & Intervention UI](./observability-intervention-ui.md) — the dashboard-side observability surface.
- [Deploy UX Improvements](./deploy-ux-improvements.md) — related operational ergonomics.
