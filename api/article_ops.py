from datetime import datetime, timezone
from api.db_constants import MONGO_GT, MONGO_IN
from api.db import fetch_from_couchdb


def _get_article_ids_from_issue(issue_id):
    """
    Recursively extract article IDs (message links) from an issue and its nested issues.
    """
    issue = fetch_from_couchdb("issues", issue_id)
    if not issue:
        return None
    
    article_links = []
    for premise in issue.get("premises", []):
        if premise.get("type") == "message":
            article_links.append(premise.get("id"))
        elif premise.get("type") == "issue":
            nested_links = _get_article_ids_from_issue(premise.get("id"))
            if nested_links:
                article_links.extend(nested_links)
    
    return list(set(article_links))


def build_article_selector(since=None, feed_id=None, issue_id=None):
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
    if issue_id:
        found_ids = _get_article_ids_from_issue(issue_id)
        if found_ids is None:
            return {"_id": {"$eq": "no_match"}}
        article_ids = found_ids

    if article_ids:
        # Note: 'id' in premises is actually the article 'link' in our current article schema
        # but articles are stored with URL-based IDs. Let's ensure consistency.
        selector["link"] = {MONGO_IN: list(set(article_ids))}
    elif issue_id:
        return {"_id": {"$eq": "no_match"}}

    if feed_id:
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
