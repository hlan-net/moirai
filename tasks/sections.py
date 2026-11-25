"""Stream sections: a fixed editorial split of the article flow (issue #266).

Every article gets exactly one ``section`` at ingestion. The signals, in
order of reliability:

1. ``feed``   - the feed's ``category`` names a section (``sports`` feed).
2. ``path``   - the article URL encodes the section (``hs.fi/urheilu/...``),
                or the whole host is one section (``kauppalehti.fi``).
3. ``topic``  - the annotation topic, closed vocabulary from ``tasks.annotator``.
                Arrives asynchronously, so an article may move out of Top
                stories a few seconds after it first appears.
4. ``default`` - ``main`` (Top stories).

Top stories is a partition, not a union: it holds everything that is not
sports, culture or business. The signal that decided the section is stored
next to it as ``section_source`` so a later, weaker signal never overrides
a stronger one.

This module has no Flask or CouchDB dependencies so the API, the workers
and the backfill script can share it.
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable, Optional
from urllib.parse import urlsplit

SECTION_MAIN = "main"
SECTION_SPORTS = "sports"
SECTION_CULTURE = "culture"
SECTION_BUSINESS = "business"

SECTIONS: tuple[str, ...] = (
    SECTION_MAIN,
    SECTION_SPORTS,
    SECTION_CULTURE,
    SECTION_BUSINESS,
)
DEFAULT_SECTION = SECTION_MAIN

SOURCE_FEED = "feed"
SOURCE_PATH = "path"
SOURCE_TOPIC = "topic"
SOURCE_DEFAULT = "default"

# Version of the sectioning rules in this module (feed categories, URL paths,
# topics). Bump it when a rule changes: the worker then re-scans every stored
# article once on its next start instead of only those without a section.
SECTION_RULES_VERSION = 1

# Generation of the revision that a re-filing wrote; see ``mark_section_rewrite``.
SECTION_REWRITE_FIELD = "section_rewrite_gen"

# Feed ``category`` values that name a section. Anything else (``tech``,
# ``imported``, free text) is kept on the feed but contributes nothing here.
FEED_CATEGORY_SECTIONS: dict[str, str] = {
    "general": SECTION_MAIN,
    "main": SECTION_MAIN,
    "news": SECTION_MAIN,
    "sports": SECTION_SPORTS,
    "sport": SECTION_SPORTS,
    "urheilu": SECTION_SPORTS,
    "culture": SECTION_CULTURE,
    "kulttuuri": SECTION_CULTURE,
    "arts": SECTION_CULTURE,
    "entertainment": SECTION_CULTURE,
    "viihde": SECTION_CULTURE,
    "business": SECTION_BUSINESS,
    "talous": SECTION_BUSINESS,
    "finance": SECTION_BUSINESS,
    "economy": SECTION_BUSINESS,
}

# Whole hosts that publish a single section (``www.`` is stripped first).
HOST_SECTIONS: dict[str, str] = {
    "kauppalehti.fi": SECTION_BUSINESS,
    "talouselama.fi": SECTION_BUSINESS,
    "taloussanomat.fi": SECTION_BUSINESS,
    "arvopaperi.fi": SECTION_BUSINESS,
    "urheilulehti.fi": SECTION_SPORTS,
}

# First path segment -> section: HS-style section paths and the usual English
# section slugs. Yle, MTV and Iltalehti article URLs carry no such segment and
# rely on the feed category or the annotation topic (docs/stream-sections.md).
PATH_SEGMENT_SECTIONS: dict[str, str] = {
    "urheilu": SECTION_SPORTS,
    "sport": SECTION_SPORTS,
    "sports": SECTION_SPORTS,
    "kulttuuri": SECTION_CULTURE,
    "culture": SECTION_CULTURE,
    "arts": SECTION_CULTURE,
    "viihde": SECTION_CULTURE,
    "entertainment": SECTION_CULTURE,
    "talous": SECTION_BUSINESS,
    "taloussanomat": SECTION_BUSINESS,
    "business": SECTION_BUSINESS,
    "economy": SECTION_BUSINESS,
}

# Annotation topic (closed vocabulary, tasks.annotator.TOPIC_VOCABULARY)
# -> section. Topics outside this map leave the article in Top stories.
TOPIC_SECTIONS: dict[str, str] = {
    "sports": SECTION_SPORTS,
    "culture": SECTION_CULTURE,
    "entertainment": SECTION_CULTURE,
    "business": SECTION_BUSINESS,
    "finance": SECTION_BUSINESS,
}

# Redis keys that hold rendered stream output (the feed's ``<item>`` elements,
# not the channel header); cleared whenever an article
# is stored, deleted or moves section.
STREAM_DEFAULT_LIMIT = 100
# ``limit`` values of ``/api/stream.rss`` whose output is cached: the RSS
# default and the Stream page's ``RSS_LIMIT`` (``ui/src/components/StreamPage.vue``).
STREAM_CACHED_LIMITS: tuple[int, ...] = (STREAM_DEFAULT_LIMIT, 200)


def parse_sections(value: Optional[str]) -> tuple[str, ...]:
    """The sections named by ``/api/stream.rss?section=``, in ``SECTIONS`` order.

    ``value`` is a comma-separated list (``sports,culture``, #344). Duplicates
    and blanks are dropped. An empty value, or every section, is the whole
    stream and returns ``()``: the sections are a partition, so their union is
    everything. An unknown name raises ``ValueError``.
    """
    names = {part.strip() for part in (value or "").split(",") if part.strip()}
    unknown = sorted(names - set(SECTIONS))
    if unknown:
        raise ValueError(f"unknown section(s): {', '.join(unknown)}")
    chosen = tuple(section for section in SECTIONS if section in names)
    return () if len(chosen) == len(SECTIONS) else chosen


def stream_cache_key(sections: str | Iterable[str] | None, limit: int) -> Optional[str]:
    """Redis key for the rendered stream items, or ``None`` when ``limit`` is not cached.

    ``sections`` is one section, several, or none for the whole stream. The key
    is built from them in ``SECTIONS`` order, so one choice has one key
    whatever order it was made in. The key space is closed (combinations of
    sections x cached limits) so every key can be listed in
    ``STREAM_CACHE_KEYS`` and invalidated with one ``DEL``.
    """
    if limit not in STREAM_CACHED_LIMITS:
        return None
    if isinstance(sections, str):
        sections = (sections,)
    names = set(sections or ())
    chosen = [section for section in SECTIONS if section in names]
    if len(chosen) == len(SECTIONS):
        chosen = []
    key = f"stream_rss_items:{','.join(chosen)}" if chosen else "stream_rss_items"
    return key if limit == STREAM_DEFAULT_LIMIT else f"{key}@{limit}"


# Every choice of sections that has its own cache entry: the whole stream
# (``()``) and each proper, non-empty subset of ``SECTIONS``.
_SECTION_CHOICES: tuple[tuple[str, ...], ...] = tuple(
    choice for size in range(len(SECTIONS)) for choice in combinations(SECTIONS, size)
)

STREAM_CACHE_KEYS: tuple[str, ...] = (
    *(
        stream_cache_key(choice, limit)
        for choice in _SECTION_CHOICES
        for limit in STREAM_CACHED_LIMITS
    ),
    "articles_default_json",
)


def is_valid_section(value: object) -> bool:
    return isinstance(value, str) and value in SECTIONS


def section_from_feed_category(category: Optional[str]) -> Optional[str]:
    """Section named by a feed category, or None when the category is free text.

    ``general`` (the default category) maps to ``main`` on purpose: a feed
    explicitly filed under general is a Top-stories feed, but that only
    matters for articles whose URL has no section of its own, so callers
    treat a ``main`` feed category as "no opinion" (see ``resolve_section``).
    """
    if not category:
        return None
    return FEED_CATEGORY_SECTIONS.get(category.strip().lower())


def section_from_link(link: Optional[str]) -> Optional[str]:
    """Section encoded in the article URL (host or first path segment)."""
    if not link:
        return None
    try:
        parts = urlsplit(link)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in HOST_SECTIONS:
        return HOST_SECTIONS[host]
    segments = [segment for segment in parts.path.split("/") if segment]
    if not segments:
        return None
    return PATH_SEGMENT_SECTIONS.get(segments[0].lower())


def section_from_topics(topics: Optional[Iterable[object]]) -> Optional[str]:
    """Section named by the first annotation topic that maps to one."""
    if not topics:
        return None
    for topic in topics:
        if isinstance(topic, str):
            section = TOPIC_SECTIONS.get(topic.strip().lower())
            if section:
                return section
    return None


def resolve_section(
    feed_category: Optional[str] = None,
    link: Optional[str] = None,
    topics: Optional[Iterable[object]] = None,
) -> tuple[str, str]:
    """Return ``(section, source)`` for an article.

    A section-specific feed wins outright. A ``general``/``main`` feed
    category is not a decision: its articles still get their section from
    the URL or the annotation, which is what mixed feeds such as
    ``hs.fi/rss/tuoreimmat.xml`` need.
    """
    from_feed = section_from_feed_category(feed_category)
    if from_feed and from_feed != SECTION_MAIN:
        return from_feed, SOURCE_FEED

    from_link = section_from_link(link)
    if from_link:
        return from_link, SOURCE_PATH

    from_topics = section_from_topics(topics)
    if from_topics:
        return from_topics, SOURCE_TOPIC

    return DEFAULT_SECTION, SOURCE_DEFAULT


def apply_topic_section(doc: dict, topics: Optional[Iterable[object]]) -> bool:
    """Re-section ``doc`` from annotation topics if no stronger signal decided it.

    Returns True when ``section`` or ``section_source`` changed. Feed and
    path decisions are never overridden; a default decision moves to the
    topic's section when there is one, and otherwise keeps its
    ``main``/``default`` stamp.

    A document that predates sectioning has no ``section_source`` and was
    never checked against its URL, so it is resolved from the link and the
    topics; otherwise e.g. a legacy ``/urheilu/`` article annotated before
    the backfill would be filed by topic and then skipped by the backfill.
    The feed category is not known here; the backfill applies it later.
    """
    source = doc.get("section_source")
    if source in (SOURCE_FEED, SOURCE_PATH):
        return False
    if source is None:
        new_section, new_source = resolve_section(None, doc.get("link"), topics)
    else:
        from_topics = section_from_topics(topics)
        if from_topics:
            new_section, new_source = from_topics, SOURCE_TOPIC
        else:
            new_section, new_source = DEFAULT_SECTION, SOURCE_DEFAULT
    if doc.get("section") == new_section and source == new_source:
        return False
    doc["section"] = new_section
    doc["section_source"] = new_source
    return True


def _rev_generation(rev: object) -> Optional[int]:
    """The generation number of a CouchDB ``_rev`` (``"7-abc"`` -> 7)."""
    if not isinstance(rev, str):
        return None
    prefix = rev.partition("-")[0]
    return int(prefix) if prefix.isdigit() else None


def mark_section_rewrite(doc: dict) -> None:
    """Stamp ``doc`` so the revision about to be written reads as a re-filing.

    Re-sectioning stored articles (the backfill, a feed's section change)
    rewrites them, and every rewrite shows up in ``articles/_changes`` exactly
    like a newly ingested article. The stamp is the generation the write will
    produce, so ``is_section_rewrite`` is true for that one revision only: any
    later update of the article bumps the generation past the stamp.
    """
    generation = _rev_generation(doc.get("_rev"))
    if generation is not None:
        doc[SECTION_REWRITE_FIELD] = generation + 1


def is_section_rewrite(doc: dict) -> bool:
    """True when this revision of ``doc`` only re-filed it into a section.

    Changes-feed consumers (agent dispatch, annotation) use it to tell a
    re-filed backlog article from one that is new.
    """
    generation = _rev_generation(doc.get("_rev"))
    return generation is not None and doc.get(SECTION_REWRITE_FIELD) == generation


def section_label(section: str) -> str:
    """Human label used in RSS channel titles."""
    return {
        SECTION_MAIN: "Top stories",
        SECTION_SPORTS: "Sports",
        SECTION_CULTURE: "Culture",
        SECTION_BUSINESS: "Business",
    }.get(section, section)


def sections_label(sections: Iterable[str]) -> str:
    """Labels of several sections for RSS channel titles: ``Sports, Culture``."""
    return ", ".join(section_label(section) for section in sections)
