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

# First path segment -> section. Covers the Finnish majors (HS, Yle, IS,
# Iltalehti, MTV) and the usual English section slugs.
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

# Redis keys that hold rendered stream output; cleared whenever an article
# is stored, deleted or moves section.
STREAM_CACHE_KEYS: tuple[str, ...] = (
    "stream_rss_xml",
    *(f"stream_rss_xml:{section}" for section in SECTIONS),
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
    path decisions are never overridden; a default decision (or a document
    that predates sectioning) moves to the topic's section when there is
    one, and otherwise just gets its ``main``/``default`` stamp.
    """
    source = doc.get("section_source")
    if source in (SOURCE_FEED, SOURCE_PATH):
        return False
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


def section_label(section: str) -> str:
    """Human label used in RSS channel titles."""
    return {
        SECTION_MAIN: "Top stories",
        SECTION_SPORTS: "Sports",
        SECTION_CULTURE: "Culture",
        SECTION_BUSINESS: "Business",
    }.get(section, section)
