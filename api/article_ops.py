from datetime import datetime, timezone
from api.db_constants import MONGO_GT, MONGO_IN
from api.db import query_couchdb


def _get_article_ids_from_trend(trend_id):
    trend = query_couchdb("trends", selector={"_id": trend_id}, limit=1)
    if not trend or not trend[0].get("event_ids"):
        return None
    
    events = query_couchdb(
        "events",
        selector={MONGO_IN: trend[0]["event_ids"]},
        fields=["article_links"]
    )
    ids = []
    for e in events:
        ids.extend(e.get("article_links", []))
    return ids

def _get_article_ids_from_event(event_id):
    event = query_couchdb("events", selector={"_id": event_id}, limit=1)
    return event[0].get("article_links", []) if event else None

def build_article_selector(since=None, feed_id=None, event_id=None, trend_id=None):
    """Build selector for efficient DB querying of articles."""
    selector = {"published": {MONGO_GT: None}}
    
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
            selector["published"] = {MONGO_GT: since_dt.isoformat()}
        except (ValueError, AttributeError):
            pass

    article_ids = []
    if trend_id:
        trend_ids = _get_article_ids_from_trend(trend_id)
        if trend_ids is None: return {"_id": {"$eq": "no_match"}}
        article_ids = trend_ids

    if event_id:
        event_ids = _get_article_ids_from_event(event_id)
        if event_ids is None: return {"_id": {"$eq": "no_match"}}
        article_ids = list(set(article_ids) & set(event_ids)) if article_ids else event_ids

    if article_ids:
        selector["_id"] = {MONGO_IN: list(set(article_ids))}
    elif trend_id or event_id:
        return {"_id": {"$eq": "no_match"}}

    if feed_id:
        if "_id" in selector:
            feed_articles = query_couchdb("articles", selector={"feed_id": feed_id}, fields=["_id"])
            feed_ids = [a["_id"] for a in feed_articles if "_id" in a]
            selector["_id"][MONGO_IN] = list(set(selector["_id"][MONGO_IN]) & set(feed_ids))
            if not selector["_id"][MONGO_IN]: return {"_id": {"$eq": "no_match"}}
        else:
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
