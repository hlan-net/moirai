# Moirai: guide for coding agents

Moirai is an aggregated RSS reader with an analytical layer on top. Feeds are fetched into articles, an LLM annotates them, and the Stream page shows the flow by section. Issues (events and trends) group articles into subjects; agents and MCP tools maintain them.

The name comes from the three Fates of Greek mythology. It names the layers (feeds, issues, agent execution) and nothing more: do not add mythological vocabulary to code, APIs or UI text.

## Where the rules are

**[`CLAUDE.md`](CLAUDE.md) is the single source for architecture, commands and conventions.** Read it before changing anything; it applies to every coding agent, not only to Claude. This file and the other agent files (`GEMINI.md`, `.github/copilot-instructions.md`) only point to it, so that the rules are written once.

| For | Read |
|---|---|
| Architecture, build, test, lint, conventions | [`CLAUDE.md`](CLAUDE.md) |
| What is planned and in what order | [`ROADMAP.md`](ROADMAP.md) |
| What changed and why | [`CHANGELOG.md`](CHANGELOG.md) |
| Releasing | [`docs/releasing.md`](docs/releasing.md) |
| LLM providers and the model catalog | [`docs/llm-configuration.md`](docs/llm-configuration.md) |
| Frontend styling | [`ui/STYLE_GUIDE.md`](ui/STYLE_GUIDE.md) |

## The state of the UI

Since v0.12.0 the UI is three views: Stream, Login and Settings (#375). The Dashboard, Lifespan, Chat, Agents, Sessions and Mythology views were removed from the frontend. Their backend (issues, chat, agents, sessions, approvals, MCP tools) remains, and functions return as parts of the Stream page. Do not bring a removed view back as a page of its own, and do not delete backend code only because no view uses it.

Documents about the removed views are in [`docs/archive/`](docs/archive/). They describe code that no longer exists.

## Rules that must not be missed

These are in `CLAUDE.md` with their details; they are repeated here because breaking them loses data or opens access.

- **Userspace.** Every MCP tool and API query is scoped to a userspace (UUID). MCP tools resolve and validate it with `resolve_userspace()` and `validate_userspace()`.
- **Authentication.** API routes carry an auth decorator from `api/auth.py` and a rate limit.
- **Input.** Text input is sanitised with `bleach.clean()` and validated with the Pydantic models in `api/validation.py`.
- **CouchDB updates.** Fetch the latest `_rev` first, or use `update_couchdb_doc_safe()`.
- **No whole-database reads of `articles`.** Use a Mango query with a limit, or `count_docs()`.
- **Before a commit.** Run the tests and the formatters named in `CLAUDE.md`. CI enforces `ruff`, `black --check` and `prettier --check`.

## Documentation conventions

- Root documents are in capitals (`README.md`, `ROADMAP.md`, `CHANGELOG.md`, `CLAUDE.md`, `AGENTS.md`).
- Feature and concept documents are in `docs/`, named in lowercase kebab-case, one subject per document. `ROADMAP.md` links to them.
- A document about something removed moves to `docs/archive/` rather than being deleted.
- A user-visible change gets an entry in `CHANGELOG.md`, written for a reader who was not there.
