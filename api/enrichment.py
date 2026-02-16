import logging
from api.db import query_couchdb, fetch_from_couchdb
from api.db_constants import MONGO_ELEM_MATCH, MONGO_IN

logger = logging.getLogger(__name__)


def enrich_articles_with_events_and_trends(articles):
    """
    Enriches a list of articles with their associated events and trends.
    Expected article format: dictionary with 'link' and 'feed_url' fields.
    """
    if not articles:
        return articles

    article_links = [a.get("link") for a in articles if a.get("link")]
    if not article_links:
        return articles

    events, trends, feeds = _fetch_related_data(article_links)

    article_event_map, article_link_to_trends, feed_title_map, feed_favicon_map = (
        _build_mappings(events, trends, feeds)
    )

    _apply_enrichment(
        articles,
        article_event_map,
        article_link_to_trends,
        feed_title_map,
        feed_favicon_map,
    )

    return articles


def _fetch_related_data(article_links):
    """Fetches events, trends, and feeds based on article links."""
    # Batch fetch events containing these article links
    events = []
    if article_links:
        events = query_couchdb(
            "events",
            selector={"article_links": {MONGO_ELEM_MATCH: {MONGO_IN: article_links}}},
            limit=1000,
        )

    event_ids = [e.get("_id") for e in events if e.get("_id")]

    # Batch fetch trends containing these event IDs
    trends = []
    if event_ids:
        trends = query_couchdb(
            "trends",
            selector={"event_ids": {MONGO_ELEM_MATCH: {MONGO_IN: event_ids}}},
            limit=1000,
        )

    # Pre-fetch feed info for title and favicon mapping
    feeds = fetch_from_couchdb("feeds")
    return events, trends, feeds


def _build_mappings(events, trends, feeds):
    """Builds lookup maps for enrichment."""
    feed_title_map = {
        feed.get("url"): feed.get("title") for feed in feeds if feed.get("url")
    }
    feed_favicon_map = {
        feed.get("url"): feed.get("favicon_url") for feed in feeds if feed.get("url")
    }

    # Build article link to event names and IDs mapping
    article_event_map = {}
    article_link_to_event_ids = {}

    for event in events:
        event_id = event.get("_id")
        event_name = event.get("name")
        if not event_name:
            continue

        for link in event.get("article_links", []):
            # Map link -> event names
            article_event_map.setdefault(link, []).append(event_name)

            # Map link -> event IDs (for trend lookup)
            if event_id:
                article_link_to_event_ids.setdefault(link, []).append(event_id)

    # Build event ID to trend names mapping
    event_id_to_trends = {}
    for trend in trends or []:
        trend_name = trend.get("name")
        if not trend_name:
            continue
        for event_id in trend.get("event_ids", []):
            event_id_to_trends.setdefault(event_id, []).append(trend_name)

    # Build article link to trend names mapping
    article_link_to_trends = {}
    for link, event_ids in article_link_to_event_ids.items():
        trend_names = {
            name 
            for eid in event_ids 
            if eid in event_id_to_trends 
            for name in event_id_to_trends[eid]
        }
        if trend_names:
            article_link_to_trends[link] = sorted(list(trend_names))

    return article_event_map, article_link_to_trends, feed_title_map, feed_favicon_map


def _apply_enrichment(
    articles,
    article_event_map,
    article_link_to_trends,
    feed_title_map,
    feed_favicon_map,
):
    """Applies the enrichment data to the articles list in-place."""
    for article in articles:
        feed_url = article.get("feed_url")
        if feed_url:
            article["feed_title"] = feed_title_map.get(feed_url)
            favicon = feed_favicon_map.get(feed_url)
            if favicon:
                article["feed_favicon"] = favicon

        article_link = article.get("link")
        if article_link:
            if article_link in article_event_map:
                article["events"] = article_event_map[article_link]

            if article_link in article_link_to_trends:
                article["trends"] = article_link_to_trends[article_link]


def enrich_events_with_articles(events, include_articles=True):
    """
    Enriches a list of events with full article objects.
    """
    if not (events and include_articles):
        return events

    for event in events:
        article_ids = event.get("article_ids", [])
        articles = []
        for article_id in article_ids:
            try:
                article = fetch_from_couchdb("articles", article_id)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.warning(f"Could not fetch article {article_id}: {e}")
        event["articles"] = articles
    return events


def enrich_trends_with_events(trends, include_events=True, include_articles=False):
    """
    Enriches a list of trends with full event objects, and optionally those events with articles.
    """
    if not (trends and include_events):
        return trends

    for trend in trends:
        event_ids = trend.get("event_ids", [])
        events = []
        for event_id in event_ids:
            try:
                event = fetch_from_couchdb("events", event_id)
                if event:
                    if include_articles:
                        enrich_events_with_articles([event], include_articles=True)
                    events.append(event)
            except Exception as e:
                logger.warning(f"Could not fetch event {event_id}: {e}")
        trend["events"] = events
    return trends
