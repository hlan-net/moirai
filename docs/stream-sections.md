# Stream Sections

Status: implemented (`tasks/sections.py`, unreleased). Tracking issue: #266.

## Goal

Split the Stream page into four newspaper-style sections, shown as tabs:

| Section | Finnish | Default |
|---|---|---|
| Top stories | Pääuutiset | **yes** — the tab that is open when the page loads |
| Sports | Urheilu | |
| Culture | Kulttuuri | |
| Business | Talous | |

The Stream stays a flow view. Sections are a fixed editorial split of the flow — the way a paper has a sports section — not a query or a filter the reader composes. Nothing else about the Stream model changes: no read/unread, no save, no search.

## Section assignment

Every article gets exactly one section, computed **at ingestion** and stored on the article document as `section`. The reader never waits for classification, the RSS endpoint can expose it, and the result is reproducible.

Signals, in order; the first that matches wins:

1. **Feed category.** Feeds already carry a free-text `category` (`add_feed`, default `general`). A section-specific feed (`hs.fi/rss/urheilu.xml` → `sports`) is the most reliable signal and needs no model. The category vocabulary is normalised to `general | sports | culture | business` plus free text for everything else.
2. **Link path.** Mixed feeds (`hs.fi/rss/tuoreimmat.xml`, Yle's main feed) publish all sections in one stream, but the article URL encodes the section: `hs.fi/kulttuuri/…`, `hs.fi/urheilu/…`, `hs.fi/talous/…`, `yle.fi/urheilu/…`. A small per-host path map covers the Finnish majors.
3. **Annotation topic.** Fallback for feeds with neither signal, using the closed topic vocabulary from #249 (`sports`, `culture`, `business`). This signal is the weakest (see #249 for why) and arrives asynchronously, so an article may move from Top stories to a section a few seconds after it appears.
4. **Default:** `main`.

Top stories is therefore "everything that is not sports, culture or business". It is a partition, not a union: a sports article does not also appear under Top stories. If a cross-section front page turns out to be wanted, a `priority: high` promotion rule can be added later without changing the storage model.

## API

- `GET /api/stream.rss?section=main|sports|culture|business` — filters the stream; no parameter keeps today's behaviour (all articles) so existing subscribers are unaffected.
- Each item gains `<category domain="section">sports</category>`.
- The Redis cache key becomes `stream_rss_items:{section}` (today: `stream_rss_items`).
- CouchDB: Mango index on `(section, published)`.

## UI

- Tab strip above the stream in `StreamPage.vue`; four tabs, Top stories active on load. The tab is not remembered between visits — the page always opens on Top stories, as requested.
- Each tab loads its own RSS (`?section=`) and keeps today's grouping/polling behaviour.
- Counts of unseen items per tab are out of scope (that is inbox behaviour).
- Mobile: tabs scroll horizontally; the active tab is always visible.

## Migration

- A backfill assigns `section` to existing articles with signals 1–3; articles with no signal stay `main`. **The worker runs it in the background at every start** (`run_worker.py`), so a deploy needs no manual step. It can also be run by hand:

  ```bash
  # inside the worker or API pod
  python -m scripts.backfill_sections --dry-run   # count only
  python -m scripts.backfill_sections             # default mode (what the worker runs)
  python -m scripts.backfill_sections --all       # also re-file feed-decided articles, e.g. after changing a feed's category
  ```

  The default mode recomputes every article except those a feed category decided, and writes only the ones whose section changes, so it is idempotent and cheap once everything is sectioned. Recomputing path/topic/default decisions matters because the annotator cannot see feed categories: an article it filed before the backfill ran still gets its feed's section. (The annotator itself resolves a pre-sectioning article from its URL as well as its topics.)

  It reads the `articles` database in pages of 500 and writes with `_bulk_docs`, so it is safe against the production backlog (see #288). It runs alongside the other workers: an article another writer updated in the meantime (a `_bulk_docs` `conflict`) is re-read with its fresh `_rev`, recomputed and retried up to 3 times. A stored article that fails the `validate_doc_update` rules (`forbidden`, a legacy document) is logged and skipped, since no rerun can fix it. Any other unwritten article counts as `failed`: the manual command then exits 1. The worker's background run retries a failed run (an exception such as a CouchDB timeout mid-way, or unwritten articles) after 1, 5 and 15 minutes, then logs an error and tries again at its next start.
- Feed category values already stored (`tech`, `finance`, …) are mapped where obvious (`finance` → `business`); the rest stay as free text and contribute nothing to sectioning.
- Until the backfill has finished (minutes after the first worker start), articles without a `section` appear in no tab (the `?section=` query is an equality on the stored field) but still in the unfiltered `/api/stream.rss`.

## Decisions

- The signal that decided an article's section is stored as `section_source` (`feed | path | topic | default`), so the asynchronous annotation signal only ever moves articles whose section was defaulted; it never overrides a feed or URL decision.
- The Feeds admin shows a section dropdown (General / Sports / Culture / Business) in place of the free-text category tag. A legacy free-text value stays selectable so it is not silently discarded. Changing it applies to new articles at ingestion, and the API re-files the feed's existing articles in a background thread (`start_feed_refile`: `--all` semantics, limited to that feed's `url`/`original_url` via the `feed_url` index), so moving a feed back to General also takes its articles out of the old tab.
- Path map: whole-host rules (`kauppalehti.fi`, `talouselama.fi`, `taloussanomat.fi`, `arvopaperi.fi`, `urheilulehti.fi`) plus first-path-segment rules (`urheilu`, `kulttuuri`, `talous`, `viihde`, `taloussanomat`, and the English `sport(s)`, `culture`, `arts`, `entertainment`, `business`, `economy`). This covers URLs that carry the section as their first segment, notably HS (`hs.fi/urheilu/…`, `/kulttuuri/`, `/talous/`) and Ilta-Sanomat. Sites whose article URLs carry no section segment — Yle (`yle.fi/a/74-…`), MTV (`mtvuutiset.fi/artikkeli/…`), Iltalehti sport by discipline (`iltalehti.fi/jalkapallo/…`) — fall through to the annotation topic or the feed category; give their section feeds a category.
- English label for Talous is "Business".

## Dependencies

- #249 — closed annotation topic vocabulary (signal 3). Signals 1–2 do not depend on it and cover the configured Finnish feeds.
