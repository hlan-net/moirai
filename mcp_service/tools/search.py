import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from ..core import mcp, auth_required, validate_userspace
from ..db import db_request
from api.db_constants import MONGO_REGEX, MONGO_OR
from .userspace import build_userspace_selector, extract_userspace
from ..responses import (
    success,
    validation_error,
    transient_error,
    internal_error,
)

# Database names
ISSUES_DB = "issues"
ARTICLES_DB = "articles"
COUCHDB_FIND_ENDPOINT = "/_find"

# ===== INTERNAL LOGIC =====

def _process_article_docs(docs):
    """Common logic to format article documents for tool output."""
    results = []
    for doc in docs:
        description = doc.get("description") or doc.get("summary", "")
        results.append(
            {
                "_id": doc.get("_id"),
                "title": doc.get("title", "Untitled"),
                "link": doc.get("link", ""),
                "published": doc.get("published", ""),
                "feed_title": doc.get("feed_title", "Unknown"),
                "description": description[:200],
                "language": doc.get("language", ""),
                "userspace": extract_userspace(doc),
            }
        )
    return results

def _build_date_filter(date_from, date_to):
    """Build date range filter for Mango selector."""
    date_filter = {}
    if date_from:
        from_dt = datetime.fromisoformat(date_from)
        if from_dt.tzinfo is None:
            from_dt = from_dt.replace(tzinfo=timezone.utc)
        date_filter["published"] = {"$gte": from_dt.isoformat()}

    if date_to:
        to_dt = datetime.fromisoformat(date_to)
        if to_dt.tzinfo is None:
            to_dt = to_dt.replace(tzinfo=timezone.utc)
        if "published" in date_filter:
            date_filter["published"]["$lte"] = to_dt.isoformat()
        else:
            date_filter["published"] = {"$lte": to_dt.isoformat()}

    return date_filter

def _search_issues_internal(
    query: str, userspace: str, longevity: Optional[str] = None, limit: int = 50
) -> dict:
    """Internal implementation of issue search."""
    if not query.strip():
        return validation_error("Query cannot be empty").to_dict()

    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    limit = min(limit, 100)
    safe_query = re.escape(query)

    # Mango selector
    text_selector: dict[str, Any] = {
        MONGO_OR: [
            {"logos": {MONGO_REGEX: f"(?i){safe_query}"}},
            {"description": {MONGO_REGEX: f"(?i){safe_query}"}},
        ],
    }

    if longevity:
        text_selector["longevity"] = longevity

    selector = {"$and": [build_userspace_selector(userspace), text_selector]}

    try:
        query_payload = {
            "selector": selector,
            "limit": limit,
            "fields": ["_id", "logos", "description", "premises", "longevity", "status"],
        }

        resp = db_request("POST", ISSUES_DB, COUCHDB_FIND_ENDPOINT, json_data=query_payload)

        if resp.status_code >= 500:
            return transient_error(
                message=f"Database error searching issues: HTTP {resp.status_code}",
                retry_after_ms=2000,
            ).to_dict()

        if resp.status_code != 200:
            return internal_error(
                message=f"Search failed: {resp.text}"
            ).to_dict()

        docs = resp.json().get("docs", [])

        results = []
        for doc in docs:
            results.append(
                {
                    "_id": doc.get("_id"),
                    "logos": doc.get("logos", "Untitled"),
                    "description": doc.get("description", ""),
                    "scale": doc.get("longevity"),
                    "status": doc.get("status"),
                    "premises_count": len(doc.get("premises", [])),
                }
            )

        return success(
            data={"results": results, "count": len(results), "query": query},
            message=f"Found {len(results)} issue(s) matching '{query}'",
        ).to_dict()

    except Exception as e:
        return internal_error(
            message=f"Search execution error: {str(e)}"
        ).to_dict()


# ===== SEARCH TOOLS =====

@mcp.tool()
@auth_required
def search_articles(
    query: str,
    userspace: Optional[str] = None,
    date_from: str = "",
    date_to: str = "",
    limit: int = 50,
) -> dict:
    """
    Search articles by keyword across the shared global article corpus.
    
    Searches title, description, and content fields. Multi-word queries
    match documents containing ALL terms (in any field, in any order).
    
    Args:
        query: Search keywords (space-separated for AND logic)
        userspace: Accepted for compatibility but ignored (articles are global)
        date_from: Optional ISO 8601 date to filter from
        date_to: Optional ISO 8601 date to filter to
        limit: Max results to return (capped at 200)
        
    Returns:
        Standardized MCPResponse as dict with:
        - status: success/error
        - data: {articles: [{id, title, link, published, feed_title, description}], count: int, query: str}
        - error_code: canonical code on error
    """
    if not query.strip():
        return validation_error("Query cannot be empty").to_dict()

    limit = min(limit, 200)

    # Split multi-word queries into individual terms so that e.g. "TPS ice hockey"
    # matches documents containing all three words (in any field, in any order),
    # rather than requiring the exact phrase "TPS ice hockey" to appear verbatim.
    terms = query.strip().split()
    term_selectors = []
    for term in terms:
        safe_term = re.escape(term)
        term_selectors.append(
            {
                MONGO_OR: [
                    {"title": {MONGO_REGEX: f"(?i){safe_term}"}},
                    {"description": {MONGO_REGEX: f"(?i){safe_term}"}},
                    {"content": {MONGO_REGEX: f"(?i){safe_term}"}},
                ]
            }
        )

    # All terms must match (AND), each across any of the three fields (OR)
    text_selector = {"$and": term_selectors} if len(term_selectors) > 1 else term_selectors[0]

    filters = [text_selector]

    try:
        date_filter = _build_date_filter(date_from, date_to)
        if date_filter:
            filters.append(date_filter)
    except ValueError:
        return validation_error("Invalid date format - use ISO 8601 (YYYY-MM-DD)").to_dict()

    try:
        selector = {"$and": filters} if len(filters) > 1 else filters[0]
        query_payload = {
            "selector": selector,
            "limit": limit,
            "sort": [{"published": "desc"}] if "published" in selector else None,
            "fields": [
                "_id",
                "title",
                "link",
                "published",
                "feed_title",
                "description",
                "summary",
                "language",
                "userspace",
                "namespace",
            ],
        }

        if "sort" in query_payload and not query_payload["sort"]:
            del query_payload["sort"]

        resp = db_request("POST", ARTICLES_DB, "/_find", json_data=query_payload)

        if resp.status_code >= 500:
            return transient_error(
                message=f"Database error searching articles: HTTP {resp.status_code}",
                retry_after_ms=2000,
            ).to_dict()
        
        if resp.status_code != 200:
            return internal_error(
                message=f"Search failed: {resp.text}"
            ).to_dict()

        results = _process_article_docs(resp.json().get("docs", []))

        return success(
            data={
                "articles": results,
                "count": len(results),
                "query": query,
                "date_from": date_from if date_from else None,
                "date_to": date_to if date_to else None,
            },
            message=f"Found {len(results)} article(s) matching '{query}'",
        ).to_dict()

    except Exception as e:
        return internal_error(
            message=f"Search execution error: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def get_recent_articles(
    userspace: Optional[str] = None, hours: int = 24, limit: int = 50
) -> dict:
    """
    Get most recent articles from the shared global article corpus.

    Notes:
    - `userspace` is accepted for backward compatibility with older callers,
      but it is intentionally ignored for article retrieval.

    Returns:
        Standardized MCPResponse as dict.
    """
    hours = min(hours, 168)
    limit = min(limit, 200)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    selector = {"published": {"$gte": cutoff.isoformat()}}

    try:
        query_payload = {
            "selector": selector,
            "limit": limit,
            "sort": [{"published": "desc"}],
            "fields": [
                "_id",
                "title",
                "link",
                "published",
                "feed_title",
                "description",
                "summary",
                "language",
                "userspace",
                "namespace",
            ],
        }

        resp = db_request("POST", ARTICLES_DB, COUCHDB_FIND_ENDPOINT, json_data=query_payload)

        if resp.status_code >= 500:
            return transient_error(
                message=f"Database error fetching recent articles: HTTP {resp.status_code}",
                retry_after_ms=2000,
            ).to_dict()

        if resp.status_code != 200:
            return internal_error(
                message=f"Fetch failed: {resp.text}"
            ).to_dict()

        results = _process_article_docs(resp.json().get("docs", []))

        return success(
            data={
                "articles": results,
                "count": len(results),
                "hours": hours,
            },
            message=f"Found {len(results)} article(s) from the last {hours} hours",
        ).to_dict()

    except Exception as e:
        return internal_error(
            message=f"Fetch execution error: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def search_issues(
    query: str, userspace: str, longevity: Optional[str] = None, limit: int = 50
) -> dict:
    """
    Search Issues (Resonances) by keyword within a userspace.

    Returns:
        Standardized MCPResponse as dict.
    """
    return _search_issues_internal(query, userspace, longevity, limit)


@mcp.tool()
@auth_required
def search_events(
    query: str, userspace: str, limit: int = 50
) -> dict:
    """
    (Alias for search_issues) Search events (transient issues) by keyword.

    Returns:
        Standardized MCPResponse as dict.
    """
    return _search_issues_internal(query, userspace, longevity="transient", limit=limit)


@mcp.tool()
@auth_required
def search_trends(
    query: str, userspace: str, limit: int = 20
) -> dict:
    """
    (Alias for search_issues) Search trends (temporal issues) by keyword.

    Returns:
        Standardized MCPResponse as dict.
    """
    return _search_issues_internal(query, userspace, longevity="temporal", limit=limit)
