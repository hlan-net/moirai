from datetime import datetime, timezone
from api.db_constants import MONGO_GT, MONGO_IN, MONGO_ELEM_MATCH
from api.db import query_couchdb


def build_article_selector(since=None, feed_id=None, event_id=None, trend_id=None):
    """Build selector for efficient DB querying of articles, including filtering by feed, event, and trend."""
    selector = {}

    # Handle 'since' filter
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
            selector["published"] = {MONGO_GT: since_dt.isoformat()}
        except (ValueError, AttributeError):
            pass

    # Ensure 'published' field is always in selector for index usage
    if "published" not in selector:
        selector["published"] = {MONGO_GT: None}

    # Prepare a list of article _id's if event_id or trend_id is specified
    article_ids_from_filters = []

    # Filter by trend_id (most restrictive lookup)
    if trend_id:
        trend = query_couchdb("trends", selector={"_id": trend_id}, limit=1)
        if trend:
            event_ids = trend[0].get("event_ids", [])
            if event_ids:
                # Find events that are part of this trend
                events_in_trend = query_couchdb(
                    "events",
                    selector={"_id": {MONGO_IN: event_ids}},
                    fields=["article_links"],
                )
                for event_doc in events_in_trend:
                    article_ids_from_filters.extend(event_doc.get("article_links", []))
            else:
                return {
                    "_id": {"$eq": "no_match"}
                }  # No articles if trend has no events
        else:
            return {"_id": {"$eq": "no_match"}}  # No articles if trend doesn't exist

    # Filter by event_id
    if event_id:
        event = query_couchdb("events", selector={"_id": event_id}, limit=1)
        if event:
            event_article_links = event[0].get("article_links", [])
            if trend_id:  # If trend_id also exists, intersect with trend's article_ids
                article_ids_from_filters = list(
                    set(article_ids_from_filters) & set(event_article_links)
                )
            else:  # Otherwise, use event's article_ids
                article_ids_from_filters.extend(event_article_links)

            if not article_ids_from_filters and (
                trend_id or event_id
            ):  # If a filter was applied and resulted in no matches
                return {"_id": {"$eq": "no_match"}}
        else:
            return {"_id": {"$eq": "no_match"}}  # No articles if event doesn't exist

    # Apply article_ids_from_filters if any were gathered
    if article_ids_from_filters:
        # Use $in operator for the _id field
        selector["_id"] = {
            MONGO_IN: list(set(article_ids_from_filters))
        }  # Use set to remove duplicates

    # Filter by feed_id
    if feed_id:
        if "_id" in selector:  # If event/trend filter already applied
            # We need to filter the existing article_ids by feed_id
            # This is complex with pure Mango, better to fetch articles by feed_id and intersect IDs
            feed_articles = query_couchdb(
                "articles", selector={"feed_id": feed_id}, fields=["_id"]
            )
            feed_article_ids = [a["_id"] for a in feed_articles if "_id" in a]

            # Intersect with article_ids_from_filters
            selector["_id"][MONGO_IN] = list(
                set(selector["_id"][MONGO_IN]) & set(feed_article_ids)
            )
            if not selector["_id"][MONGO_IN]:  # If intersection is empty
                return {"_id": {"$eq": "no_match"}}

        else:  # No event/trend filter, apply feed_id directly
            selector["feed_id"] = feed_id

    return selector


def paginate_results(results, limit, skip):
    """Handle has_more logic and calculate total count."""
    has_more = False
    if len(results) > limit:
        has_more = True
        results = results[:limit]

    # Total count is not available efficiently with Mango queries
    total_count = len(results) + skip + (1 if has_more else 0)

    return results, has_more, total_count
