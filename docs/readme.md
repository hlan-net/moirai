# Moirai Documentation

Moirai is an aggregated RSS reader with an analytical layer on top. The UI is three views: the Stream (the article flow, by section), Login and Settings. Issues (events and trends), chat, agents and the MCP server are the backend behind it.

## Start here, by role

| You are | Read | It covers |
|---|---|---|
| A reader | [User Guide](./tutorial-user.md) | The Stream page, its sections and menu, the side column |
| An operator | [Admin Guide](./tutorial-admin.md) | Deployment, users, feeds, agents, monitoring, backup |
| A developer | [Developer Guide](./tutorial-developer.md) and [`CLAUDE.md`](../CLAUDE.md) | Setup, architecture, adding endpoints, MCP tools and agent logic |

`CLAUDE.md` is the source for architecture and conventions; where a tutorial and `CLAUDE.md` disagree, `CLAUDE.md` is right.

## Quick start

```bash
docker compose up --build
```

The UI and the API are at `http://localhost:8088`, the MCP server at `http://localhost:8090`. Log in as the admin from `.env`, open **Settings → Feeds**, and import feeds. Articles appear on the Stream page as the scheduler fetches them.

## How it fits together

```
Feeds → Articles → Annotations (LLM) → Stream page (/api/stream.rss)
                 ↘ Issues: events and trends (agents, MCP tools)
```

- **Flask REST API** (port 8088): the UI's API and admin operations.
- **MCP server** (port 8090): tools for LLM agents; the agent orchestrator and the annotation worker run here.
- **Worker and scheduler**: fetch feeds and turn them into articles.
- **CouchDB and Redis**: storage and cache.

## Reference

| Document | Subject |
|---|---|
| [architecture.md](./architecture.md) | Components, the issue data model, data flow, deployment |
| [llm-configuration.md](./llm-configuration.md) | LLM providers, the AISA proxy, the model catalog |
| [stream-sections.md](./stream-sections.md) | How articles are filed into sections |
| [external-api.md](./external-api.md) | Using the API from outside |
| [mcp-servers-guide.md](./mcp-servers-guide.md), [mcp-tool-migration.md](./mcp-tool-migration.md) | MCP servers and the tool response contract |
| [releasing.md](./releasing.md) | The release procedure |
| [metrics-and-alerting.md](./metrics-and-alerting.md) | Planned: Prometheus metrics, alerts, Grafana |
| [observability-intervention-ui.md](./observability-intervention-ui.md) | Planned: sessions, approvals, cancellation in the UI |
| [security-enhancements.md](./security-enhancements.md) | Planned: JWT session model, RBAC, userspace isolation |
| [agentic-improvements.md](./agentic-improvements.md) | Deferred: plan-execute-reflect, agent memory |
| [social-export-bluesky.md](./social-export-bluesky.md) | Sharing to Bluesky |
| [settings-store-refactoring.md](./settings-store-refactoring.md) | The UI settings store |
| `k8s-*.md` | Kubernetes-native inference options |

What is planned, and in what order, is in [`ROADMAP.md`](../ROADMAP.md); what changed is in [`CHANGELOG.md`](../CHANGELOG.md).

## Archive

[`archive/`](./archive/) holds documents about things that no longer exist, kept for their reasoning: the Dashboard, the issue wizards, the draggable chat, and older architecture plans. Nothing in it describes the current code.
