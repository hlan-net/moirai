import json
import re
from datetime import datetime, timedelta, timezone
from ..core import mcp, auth_required, validate_namespace
from ..db import db_request
from api.db_constants import MONGO_REGEX, MONGO_OR

# ===== SEARCH TOOLS =====

def _process_article_docs(docs):
    """Common logic to format article documents for tool output."""
    results = []
    for doc in docs:
        results.append(
            {
                "_id": doc.get("_id"),
                "title": doc.get("title", "Untitled"),
                "link": doc.get("link", ""),
                "published": doc.get("published", ""),
                "feed_title": doc.get("feed_title", "Unknown"),
                "description": doc.get("description", "")[:200],
                "namespace": doc.get("namespace"),
            }
        )
    return results

def _handle_date_filters(selector, date_from, date_to):
    """Add date range filters to Mango selector."""
    if date_from:
        from_dt = datetime.fromisoformat(date_from)
        if from_dt.tzinfo is None:
            from_dt = from_dt.replace(tzinfo=timezone.utc)
        selector["published"] = {"$gte": from_dt.isoformat()}

    if date_to:
        to_dt = datetime.fromisoformat(date_to)
        if to_dt.tzinfo is None:
            to_dt = to_dt.replace(tzinfo=timezone.utc)
        if "published" in selector:
            selector["published"]["$lte"] = to_dt.isoformat()
        else:
            selector["published"] = {"$lte": to_dt.isoformat()}

@mcp.tool()
@auth_required
def search_articles(
    query: str,
    namespace: str = None,
    date_from: str = "",
    date_to: str = "",
    limit: int = 50,
    api_key: str = None,
) -> str:
    """
    Search articles by keyword. Optionally filter by namespace.

    Args:
        query: Search keywords.
        namespace: Optional GUID of the namespace.
        date_from: Optional start date (ISO).
        date_to: Optional end date (ISO).
        limit: Max results.
        api_key: Required for authentication.
    """
    if not query.strip():
        return json.dumps({"error": "Query cannot be empty"})

    limit = min(limit, 200)
    safe_query = re.escape(query)

    # Build Mango selector
    selector = {
        MONGO_OR: [
            {"title": {MONGO_REGEX: f"(?i){safe_query}"}},
            {"description": {MONGO_REGEX: f"(?i){safe_query}"}},
            {"content": {MONGO_REGEX: f"(?i){safe_query}"}},
        ]
    }

    if namespace:
        selector["namespace"] = namespace

    try:
        _handle_date_filters(selector, date_from, date_to)
    except ValueError:
        return json.dumps({"error": "Invalid date format provided."})

    try:
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
                "namespace",
            ],
        }

        if not query_payload["sort"]:
            del query_payload["sort"]

        resp = db_request("POST", "articles", "/_find", json_data=query_payload)

        if resp.status_code != 200:
            return json.dumps({"error": f"Search failed: {resp.text}"})

        results = _process_article_docs(resp.json().get("docs", []))

        return json.dumps(
            {
                "total": len(results),
                "query": query,
                "namespace": namespace,
                "results": results,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"error": f"Search execution error: {str(e)}"})


@mcp.tool()
@auth_required
def get_recent_articles(
    namespace: str = None, hours: int = 24, limit: int = 50, api_key: str = None
) -> str:
    """
    Get most recent articles. Optionally filter by namespace.

    Args:
        namespace: Optional GUID of the namespace.
        hours: How far back to look.
        limit: Max results.
        api_key: Required for authentication.
    """
    hours = min(hours, 168)
    limit = min(limit, 200)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    selector = {"published": {"$gte": cutoff.isoformat()}}
    if namespace:
        selector["namespace"] = namespace

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
                "namespace",
            ],
        }

        resp = db_request("POST", "articles", "/_find", json_data=query_payload)

        if resp.status_code != 200:
            return json.dumps({"error": f"Fetch failed: {resp.text}"})

        results = _process_article_docs(resp.json().get("docs", []))

        return json.dumps(
            {
                "total": len(results),
                "hours": hours,
                "namespace": namespace,
                "results": results,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"error": f"Fetch execution error: {str(e)}"})


@mcp.tool()
@auth_required
def search_events(
    query: str, namespace: str, limit: int = 50, api_key: str = None
) -> str:
    """
    Search events by keyword within a namespace.

    Args:
        query: Search keywords.
        namespace: GUID of the namespace.
        limit: Max results.
        api_key: Required for authentication.
    """
    if not query.strip():
        return json.dumps({"error": "Query cannot be empty"})

    valid, err = validate_namespace(namespace)
    if not valid:
        return json.dumps({"error": err})

    limit = min(limit, 100)
    safe_query = re.escape(query)

    # Mango selector
    selector = {
        "namespace": namespace,
        MONGO_OR: [
            {"name": {MONGO_REGEX: f"(?i){safe_query}"}},
            {"description": {MONGO_REGEX: f"(?i){safe_query}"}},
        ],
    }

    try:
        query_payload = {
            "selector": selector,
            "limit": limit,
            "fields": ["_id", "name", "description", "article_links"],
        }

        resp = db_request("POST", "events", "/_find", json_data=query_payload)

        if resp.status_code != 200:
            return json.dumps({"error": f"Search failed: {resp.text}"})

        docs = resp.json().get("docs", [])

        results = []
        for doc in docs:
            results.append(
                {
                    "_id": doc.get("_id"),
                    "name": doc.get("name", "Untitled"),
                    "description": doc.get("description", ""),
                    "article_count": len(doc.get("article_links", [])),
                }
            )

        return json.dumps(
            {"total": len(results), "query": query, "results": results}, indent=2
        )

    except Exception as e:
        return json.dumps({"error": f"Search execution error: {str(e)}"})


@mcp.tool()
@auth_required
def search_trends(
    query: str, namespace: str, limit: int = 20, api_key: str = None
) -> str:
    """
    Search trends by keyword within a namespace.

    Args:
        query: Search keywords.
        namespace: GUID of the namespace.
        limit: Max results.
        api_key: Required for authentication.
    """
    if not query.strip():
        return json.dumps({"error": "Query cannot be empty"})

    valid, err = validate_namespace(namespace)
    if not valid:
        return json.dumps({"error": err})

    limit = min(limit, 100)
    safe_query = re.escape(query)

    # Mango selector
    selector = {
        "namespace": namespace,
        MONGO_OR: [
            {"name": {MONGO_REGEX: f"(?i){safe_query}"}},
            {"description": {MONGO_REGEX: f"(?i){safe_query}"}},
        ],
    }

    try:
        query_payload = {
            "selector": selector,
            "limit": limit,
            "fields": ["_id", "name", "description", "event_ids"],
        }

        resp = db_request("POST", "trends", "/_find", json_data=query_payload)

        if resp.status_code != 200:
            return json.dumps({"error": f"Search failed: {resp.text}"})

        docs = resp.json().get("docs", [])

        results = []
        for doc in docs:
            results.append(
                {
                    "_id": doc.get("_id"),
                    "name": doc.get("name", "Untitled"),
                    "description": doc.get("description", ""),
                    "event_count": len(doc.get("event_ids", [])),
                }
            )

        return json.dumps(
            {"total": len(results), "query": query, "results": results}, indent=2
        )

    except Exception as e:
        return json.dumps({"error": f"Search execution error: {str(e)}"})
