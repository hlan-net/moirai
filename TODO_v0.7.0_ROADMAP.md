# Moirai v0.7.0 Roadmap

**Status:** In development (post v0.6.4)
**Hotfix branch:** v0.6.5 reserved for critical fixes against v0.6.4

---

## 🎯 v0.7.0 Focus: Social Export & Dashboard UX

### A) Social Export — Bluesky Integration (Core)

Share curated Issues to Bluesky with one click from the dashboard.

#### Phase 1: Core (v0.7.0)
- [ ] `mcp_service/tools/social_export.py` — `publish_to_bluesky` MCP tool
- [ ] `POST /api/issues/<id>/share` — REST endpoint (platform + optional content override)
- [ ] `api/validation.py` — `ShareIssueRequest` model
- [ ] Bluesky credentials stored per-userspace in user settings (app password)
- [ ] LLM-generated post text (≤300 chars) with auto-thread split if longer
- [ ] Store `social_posts.bluesky` reference back on the issue document
- [ ] `ui/src/components/IssueColumn.vue` — "Share to Bluesky" button on issue cards
- [ ] `atproto>=0.0.58` added to `environment.yml` / `requirements.txt`
- [ ] Unit tests for post generation and Bluesky client mock

#### Phase 2: Analytics (v0.7.1)
- [ ] Track post engagement (likes, reposts, replies) via Bluesky API polling
- [ ] Show engagement metrics on issue card
- [ ] Link back to Moirai via short URL / UTM params

#### Phase 3: Automation (v0.7.2+)
- [ ] SCHEDULED agent: auto-post daily digest of top issues
- [ ] Customizable post templates per userspace

---

### B) Dashboard UX Improvements (v0.7.0)

Items identified during v0.6.x development:

#### Chat drawer
- [ ] Draggable chat drawer — pointer event drag on header, `position: fixed` with dynamic top/left, boundary clamping, touch support (`useDraggable` composable)

#### Quick actions (context chat buttons)
- [ ] **Article → "Find Related Issues"** — search existing issues and suggest linking
- [ ] **Article → "Summarize in 3 bullets"** — single-turn, result shown inline
- [ ] **Issue → "Find more coverage"** — search recent articles matching this issue
- [ ] **Issue → "Write a brief"** — 2-3 paragraph press brief from linked articles
- [ ] **Issue → "Seal this issue"** — guided close flow: summary → set eternal + passed_at

#### River of News
- [ ] UI toggle/selector to switch between view modes (Pure River / Time-Blocked / AI-Annotated)

#### LLM endpoint diagnostics
- [ ] Lightweight reachability test in Settings before sending chat requests
- [ ] Clear error messages for DNS failures, timeout, wrong port

---

## Architecture Notes

### Bluesky Auth
- User provides app password (from bsky.app → Settings → App Passwords)
- Stored in user settings doc in CouchDB (same as OpenAI/Gemini API keys)
- No OAuth flow needed for v0.7.0

### Bluesky Post Flow
```
Issue card [Share button]
  → POST /api/issues/<id>/share  {platform: "bluesky"}
  → chat agent calls publish_to_bluesky MCP tool
  → tool fetches issue + articles, calls LLM for post text
  → submits via atproto Client
  → stores post URI back on issue doc
  → returns post URL to UI
```

### Files to create/modify
- `mcp_service/tools/social_export.py` (new)
- `api/routes.py` — add share endpoint
- `api/validation.py` — ShareIssueRequest
- `ui/src/components/IssueColumn.vue` — share button
- `ui/src/composables/useDraggable.ts` (new) — drag logic
- `ui/src/components/ContextChatModal.vue` — apply draggable
- `environment.yml` / `requirements.txt` — atproto dep

---

## v0.8.0+ Candidates

- Multi-platform (Mastodon, Slack/Discord webhooks)
- Batch/digest sharing (daily top-3 issues)
- Engagement analytics feedback loop into issue importance scoring
