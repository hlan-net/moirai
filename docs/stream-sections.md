# Stream Sections

Status: proposed (roadmap). Tracking issue: #266.

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
- The Redis cache key becomes `stream_rss_xml:{section}` (today: `stream_rss_xml`).
- CouchDB: Mango index on `(section, published)`.

## UI

- Tab strip above the stream in `StreamPage.vue`; four tabs, Top stories active on load. The tab is not remembered between visits — the page always opens on Top stories, as requested.
- Each tab loads its own RSS (`?section=`) and keeps today's grouping/polling behaviour.
- Counts of unseen items per tab are out of scope (that is inbox behaviour).
- Mobile: tabs scroll horizontally; the active tab is always visible.

## Migration

- A one-off backfill assigns `section` to existing articles with signals 1–3; articles with no signal stay `main`.
- Feed category values already stored (`tech`, `finance`, …) are mapped where obvious (`finance` → `business`); the rest stay as free text and contribute nothing to sectioning.

## Open questions

- Should the Feeds admin let the user pick the section from a dropdown instead of free text? Probably yes, in the same change.
- Which hosts go in the initial path map? HS, Yle, IS, Kauppalehti, Taloussanomat are the obvious Finnish ones.
- Is "Business" the right English label for Talous, or "Economy"? Cosmetic; decide in the PR.

## Dependencies

- #249 — closed annotation topic vocabulary (signal 3). Signals 1–2 do not depend on it and cover the configured Finnish feeds.
