from datetime import datetime, timezone
from api.db_constants import MONGO_GT

def build_article_selector(since=None):
    """Build selector for efficient DB querying of articles."""
    selector = {}
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            # Ensure timezone awareness
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
            selector["published"] = {"$gt": since_dt.isoformat()}
        except (ValueError, AttributeError):
            pass  # Invalid since parameter, ignore

    # Ensure we have a selector for sorting field to optimize index usage
    if "published" not in selector:
        selector["published"] = {MONGO_GT: None}
    
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
