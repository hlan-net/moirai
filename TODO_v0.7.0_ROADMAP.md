# Moirai v0.7.0 Roadmap

**Status:** In development (post v0.6.5)
**Target:** `release/v0.7.0` branch — feature branches merge here, then release/v0.7.0 → main

---

## Branching Strategy

All feature work uses dedicated branches that PR into `release/v0.7.0`.
Quality gates (SonarCloud, pytest, Playwright) run on every PR.
Final `release/v0.7.0 → main` PR triggers the v0.7.0 release.

| Branch | PR | Status |
|--------|----|--------|
| `feat/userspace-document` | #113 | ✅ Open, CI running |
| `feat/session-logging` | — | 🔲 Not started |
| `feat/chat-llm-override` | — | 🔲 Not started |
| `feat/quick-actions` | — | 🔲 Not started |
| `feat/bluesky-export` | — | 🔲 Not started |
| `feat/draggable-chat` | — | 🔲 Not started |

---

## Implementation Order (dependency-aware)

1. **feat/userspace-document** ← foundational, all others depend on it
2. **feat/session-logging** ← depends on userspace (resolves llm_config for log entries)
3. **feat/chat-llm-override** ← depends on userspace (override the default)
4. **feat/quick-actions** ← independent, can run in parallel with 2 & 3
5. **feat/bluesky-export** ← largest, start after foundations are merged
6. **feat/draggable-chat** ← pure UX polish, last

---

## Feature 1: Userspace Document (feat/userspace-document) ✅ PR #113

**What:** Userspace document is now the authoritative source for LLM credentials
and preferences. One userspace per user (same UUID as existing data — zero migration
risk). Multiple userspaces per user supported by the data model.

**Architecture:**
- `userspaces` CouchDB DB — doc `_id` = userspace UUID (same as feeds/articles/issues `userspace` field)
- `api/userspace_ops.py` — `resolve_llm_config(userspace_id)`, migration helper
- `api/userspace_routes.py` — CRUD at `GET/POST /api/userspaces`, `GET/PATCH/DELETE /api/userspaces/<id>`
- `api/validation.py` — `LLMConfigRequest`, `UserspaceCreateRequest`, `UserspaceUpdateRequest`
- Migration runs on startup (idempotent): creates userspace doc for each existing user

**LLM config keys in `userspace.llm_config`:**
```json
{
  "provider": "ollama | openai | gemini",
  "model": "llama3.1",
  "openai_api_key": "sk-...",
  "gemini_api_key": "...",
  "ollama_endpoint": "http://host.docker.internal:11434/v1"
}
```

**What was removed from old locations:**
- Chat routes no longer read LLM keys from `user.settings`
- Agent orchestrator no longer uses `agent_config.llm_model_config`
- Both now call `resolve_llm_config(userspace_id)` instead

---

## Feature 2: Session Logging (feat/session-logging)

**What:** Every agent execution and chat request is a "session" — a structured log
entry stored in Redis with a 7-day TTL. Replaces the in-memory scheduler log ringbuffer.

**Session types:** `scheduled_agent`, `on_new_article`, `chat`

**Redis key structure:**
```
session:log:{session_id}       → JSON blob (TTL 7 days)
session:index:{userspace}      → sorted set of session_ids scored by timestamp
session:index:all              → sorted set of all session_ids (admin view)
```

**Session schema:**
```json
{
  "session_id": "uuid",
  "session_type": "scheduled_agent | on_new_article | chat",
  "userspace": "uuid",
  "agent_config_id": "uuid or null",
  "agent_name": "create_event_from_articles",
  "trigger": "schedule_interval=1h | new_articles=3 | user",
  "started_at": "ISO8601",
  "finished_at": "ISO8601",
  "duration_ms": 1234,
  "status": "running | completed | error",
  "error": "traceback or null",
  "resolved_llm": {"provider": "openai", "model": "gpt-4o", "source": "userspace"},
  "llm_calls": [{"provider": "...", "model": "...", "duration_ms": 890}],
  "tool_calls": [{"name": "add_event", "status": "ok", "duration_ms": 45}],
  "articles_processed": 3
}
```

**Files to create/modify:**
- `tasks/session_logger.py` (new) — `SessionLogger` class wrapping Redis ops
- `tasks/agent_orchestrator.py` — instrument `execute_agent_logic()` with session start/finish
- `api/chat_routes.py` — instrument `_run_agent_loop()` with session start/finish
- `api/routes.py` — `GET /api/sessions` and `GET /api/sessions/<id>` endpoints
- `tasks/scheduler_log.py` — can be retired (replaced by session logging)

**API:**
```
GET /api/sessions                    → list sessions (admin, paginated, filter by userspace)
GET /api/sessions/<session_id>       → full session detail
```

**UI:** Settings page → replace "Scheduler Logs" tab with "Agent Sessions" tab showing
filterable table (type, agent name, status, duration) with expandable tool/LLM call traces.

---

## Feature 3: Chat LLM Override (feat/chat-llm-override)

**What:** Per-chat model/provider selector in the chat drawer that defaults to the
userspace config but can be changed for that session only.

**UI:** Small dropdown in chat drawer header showing current provider:model, clickable
to change. Selection resets when drawer closes.

**Backend:** Already works — `chat()` endpoint accepts `llm_endpoint` and `model` in
request body as overrides over userspace defaults (implemented in feat/userspace-document).

**Files to modify:**
- `ui/src/components/ContextChatModal.vue` — add provider:model selector to header
- `ui/src/stores/settings.ts` — expose available providers for the dropdown

---

## Feature 4: Quick Actions (feat/quick-actions)

**What:** Additional quick action buttons in the context chat modal.

**Current quick actions (already shipped in v0.6.5):**
- Article → "Raise as Issue" (wizard)
- Issue → "Refine Description"
- Issue → "Find new coverage"
- Feed → "What's new?"

**New quick actions to add:**
| Context | Label | Behaviour |
|---------|-------|-----------|
| Article | "Find Related Issues" | Search existing issues and suggest linking |
| Article | "Summarize in 3 bullets" | Single-turn, result shown inline |
| Issue | "Write a brief" | 2-3 paragraph press brief from linked articles |
| Issue | "Seal this issue" | Guided close: summary → call `seal_issue` tool |

**Files to modify:**
- `ui/src/components/ContextChatModal.vue` — add to `quickActions` arrays

---

## Feature 5: Bluesky Social Export (feat/bluesky-export)

**What:** Share curated issues to Bluesky in one click.

**Auth:** App password (from bsky.app Settings → App Passwords). Stored in
`userspace.llm_config` or as a separate `userspace.social_credentials.bluesky` field.
No OAuth needed for v0.7.0.

**Post flow:**
```
Issue card [Share to Bluesky]
  → POST /api/issues/<id>/share  {platform: "bluesky"}
  → fetch issue + linked articles
  → call LLM to generate post text (≤300 chars)
  → submit via atproto Client
  → store post URI back on issue doc (social_posts.bluesky)
  → return post URL to UI
```

**Files to create/modify:**
- `mcp_service/tools/social_export.py` (new) — `publish_to_bluesky` MCP tool
- `api/routes.py` — `POST /api/issues/<id>/share`
- `api/validation.py` — `ShareIssueRequest`
- `ui/src/components/IssueColumn.vue` — "Share to Bluesky" button on issue cards
- `environment.yml` / `requirements.txt` — `atproto>=0.0.58`

**Bluesky credentials location (decision needed):**
Store as `userspace.bluesky_handle` + `userspace.bluesky_app_password` on the
userspace document (consistent with LLM config being on userspace).

**Phases:**
- Phase 1 (v0.7.0): core post — ✅ in scope
- Phase 2 (v0.7.1): engagement analytics
- Phase 3 (v0.7.2+): scheduled auto-digest agent

---

## Feature 6: Draggable Chat Drawer (feat/draggable-chat)

**What:** Chat drawer can be dragged to any position on screen.

**Implementation:**
- `ui/src/composables/useDraggable.ts` (new) — pointer events on header, boundary clamping
- `ui/src/components/ContextChatModal.vue` — apply composable to drawer header

---

## What Was Dropped from Old Roadmap

- **Traditional form wizard** — chat + direct fast-path already cover the use case well.
  Can revisit if user feedback demands it.
- **River of News view selector** — deferred to v0.8.0. ArticleColumn already works well.

---

## v0.8.0+ Candidates

- River of News (Pure / Time-Blocked / AI-Annotated toggle)
- Bluesky Phase 2–3 (analytics, auto-digest agent)
- Multi-platform social export (Mastodon, Slack/Discord webhooks)
- Multiple userspaces per user — UI switcher in top bar
- Cross-userspace read-only issue sharing
