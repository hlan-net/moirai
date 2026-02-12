from flask import Blueprint, jsonify, abort, request, Response
import os
import hashlib
import version
import requests
from datetime import datetime, timezone
from functools import wraps
from api.extensions import limiter
from tasks.fetch_feed_task import FetchFeedTask
from tasks.favicon_fetcher import fetch_favicon_url
from .db import fetch_from_couchdb, delete_from_couchdb, update_couchdb_doc, query_couchdb
from pydantic import ValidationError
from .validation import (
    FeedCreateRequest, FeedUpdateRequest,
    EventCreateRequest, EventUpdateRequest,
    TrendCreateRequest, TrendUpdateRequest,
    ConfigUpdateRequest
)

from api.enrichment import enrich_articles_with_events_and_trends
from api.feed_ops import process_bulk_import_url
from api.rss_ops import generate_rss_item_xml

api_blueprint = Blueprint('api', __name__)

API_USERNAME = os.environ.get("API_USERNAME")
API_PASSWORD = os.environ.get("API_PASSWORD")
ALLOW_PUBLIC_READ_ENV = os.environ.get("ALLOW_PUBLIC_READ", "false").lower() == "true"
ITERATION_INTERVAL_ENV = int(os.environ.get("ITERATION_INTERVAL", 600))

# Constants for error messages
ERROR_FEED_NOT_FOUND = "Feed not found"
ERROR_LIMIT_INTEGER = "limit must be an integer"
ERROR_QUERY_REQUIRED = "Query parameter 'q' is required"

def parse_datetime_safe(date_str):
    """Parse datetime and ensure it's timezone-aware for comparison."""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        # If naive (no timezone), assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        # Return a very old date for invalid dates so they sort last
        return datetime.min.replace(tzinfo=timezone.utc)

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid."""
    return username == API_USERNAME and password == API_PASSWORD

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def get_config_doc():
    """Helper to get the main config doc. Returns None if config doesn't exist or DB is unavailable."""
    return fetch_from_couchdb("config", "main")

def get_public_read_setting():
    """Checks DB for config, falls back to env var."""
    config = get_config_doc()
    if config and "allow_public_read" in config:
        return config["allow_public_read"]
    return ALLOW_PUBLIC_READ_ENV

def get_iteration_interval_setting():
    """Checks DB for config, falls back to env var."""
    config = get_config_doc()
    if config and "iteration_interval" in config:
        try:
            return int(config["iteration_interval"])
        except (ValueError, TypeError):
            pass
    return ITERATION_INTERVAL_ENV

@api_blueprint.route("/health", methods=["GET"])
@limiter.exempt
def health_check():
    return jsonify({"status": "healthy"})

# Apply auth to all routes in this blueprint
@api_blueprint.before_request
def before_request_auth():
    if request.method == "OPTIONS":
        return # Allow CORS preflight if needed
    
    # Allow health check without auth
    if request.endpoint == "api.health_check":
        return None
    
    # Allow RSS feed without auth (RSS feeds are typically public)
    if request.endpoint == "api.rss_feed":
        return None

    # Optional public read access for articles and feeds only
    if request.method == "GET" and request.endpoint in ["api.list_articles", "api.list_feeds"]:
         if get_public_read_setting():
             return None

    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

# --- Feeds ---
@api_blueprint.route("/feeds", methods=["POST"])
def create_feed():
    try:
        validated = FeedCreateRequest(**request.json)
    except ValidationError as e:
        abort(400, description=str(e))
        
    feed_url = str(validated.url)
    # Generate ID
    feed_id = hashlib.sha256(feed_url.encode('utf-8')).hexdigest()
    
    # Fetch favicon for the feed
    favicon_url = fetch_favicon_url(feed_url)
    
    feed_doc = {
        "_id": feed_id,
        "url": feed_url,
        "title": validated.title,
        "category": validated.category or "general",
        "added_at": datetime.now(timezone.utc).isoformat(),
        "favicon_url": favicon_url
    }
    
    if update_couchdb_doc("feeds", feed_id, feed_doc):
        return jsonify(feed_doc), 201
    else:
        abort(500, description="Failed to create feed")

@api_blueprint.route("/feeds", methods=["GET"])
@limiter.limit("10 per minute")
def list_feeds():
    feeds = fetch_from_couchdb("feeds")
    return jsonify(feeds)

@api_blueprint.route("/feeds/<feed_id>", methods=["DELETE"])
def delete_feed(feed_id):
    feed = fetch_from_couchdb("feeds", feed_id)
    if not feed:
        abort(404, description=ERROR_FEED_NOT_FOUND)
    
    if delete_from_couchdb("feeds", feed_id, feed["_rev"]):
        return jsonify({"status": "deleted"})
    else:
        abort(500, description="Failed to delete feed")

@api_blueprint.route("/feeds/<feed_id>", methods=["PUT"])
def update_feed(feed_id):
    feed = fetch_from_couchdb("feeds", feed_id)
    if not feed:
        abort(404, description=ERROR_FEED_NOT_FOUND)
    
    # Validate input
    try:
        validated = FeedUpdateRequest(**request.json)
    except ValidationError as e:
        abort(400, description=str(e))
    
    feed["title"] = validated.title
    
    if update_couchdb_doc("feeds", feed_id, feed):
        return jsonify(feed)
    else:
        abort(500, description="Failed to update feed")

@api_blueprint.route("/feeds/refresh", methods=["POST"])
@requires_auth
def refresh_feeds():
    """Triggers a background refresh of all registered feeds."""
    feeds = fetch_from_couchdb("feeds")
    if not feeds:
        return jsonify({"status": "no feeds found", "count": 0})
    
    count = 0
    for feed in feeds:
        url = feed.get("url")
        if url:
            # Run in background thread (FetchFeedTask inherits from threading.Thread)
            task = FetchFeedTask(url)
            task.start()
            count += 1
            
    return jsonify({"status": "started", "count": count})

@api_blueprint.route("/feeds/refresh/<path:feed_url>", methods=["POST"])
@requires_auth
@limiter.limit("10 per minute")
def refresh_single_feed(feed_url):
    """Triggers a background refresh of a single feed by URL."""
    # Validate the feed exists efficiently
    selector = {"url": feed_url}
    existing_feeds = query_couchdb("feeds", selector=selector, limit=1)
    
    if not existing_feeds:
        abort(404, description=ERROR_FEED_NOT_FOUND)
    
    # Run in background thread
    task = FetchFeedTask(feed_url)
    task.start()
    
    return jsonify({"status": "started", "url": feed_url})

@api_blueprint.route("/feeds/bulk", methods=["POST"])
@limiter.limit("5 per minute")  # Strict rate limit for bulk operations
def bulk_import_feeds():
    """Import multiple feeds from a list of URLs. Limited to 50 URLs per request."""
    # Validate request body
    if not request.json:
        abort(400, description="Request body must be JSON")
    
    data = request.json
    urls = data.get("urls", [])
    
    if not urls or not isinstance(urls, list):
        abort(400, description="Expected 'urls' as an array")
    
    # Security: Limit bulk import size to prevent DoS
    MAX_BULK_IMPORT_SIZE = 50
    if len(urls) > MAX_BULK_IMPORT_SIZE:
        abort(400, description=f"Too many URLs. Maximum {MAX_BULK_IMPORT_SIZE} URLs per request.")
    
    results = {
        "total": len(urls),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": []
    }
    
    for url_str in urls:
        result = process_bulk_import_url(url_str)
        if result["status"] == "success":
            results["success"] += 1
        elif result["status"] == "skipped":
            results["skipped"] += 1
        elif result["status"] == "failed":
            results["failed"] += 1
            results["errors"].append({"url": url_str, "error": result["error"]})
    
    return jsonify(results), 200

# --- Articles ---
@api_blueprint.route("/articles", methods=["GET"])
def list_articles():
    # Pagination parameters
    try:
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
    except ValueError:
        abort(400, description="limit and skip must be integers")
    since = request.args.get('since')  # ISO timestamp to fetch only newer articles
    
    # Validate pagination params
    limit = min(max(limit, 1), 200)  # Clamp between 1-200
    skip = max(skip, 0)
    
    
    # Build selector for efficient DB querying
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
        selector["published"] = {"$gt": None}



    # Query CouchDB directly with pagination and sorting
    # We fetch limit + 1 to determine if there are more results
    articles = query_couchdb(
        "articles", 
        selector=selector, 
        limit=limit + 1, 
        skip=skip, 
        sort=[{"published": "desc"}]
    )

    # Handle has_more logic
    has_more = False
    if len(articles) > limit:
        has_more = True
        articles = articles[:limit]
    
    paginated_articles = articles
    # Total count is not available efficiently with Mango queries
    total_count = len(articles) + skip + (1 if has_more else 0)
    
    # Enrichment
    enrich_articles_with_events_and_trends(paginated_articles)
    
    return jsonify({
        "articles": paginated_articles,
        "total_count": total_count,
        "has_more": (skip + limit) < total_count,
        "limit": limit,
        "skip": skip
    })

@api_blueprint.route("/stream.rss", methods=["GET"])
def rss_feed():
    """Generate RSS 2.0 feed for the aggregated article stream. Public endpoint (no auth required)."""
    from xml.sax.saxutils import escape
    
    # Fetch all data (reuse logic from list_articles)
    limit = int(request.args.get('limit', 100))  # Default to 100 items for RSS
    limit = min(max(limit, 1), 500)  # Clamp between 1-500
    


    # Query CouchDB directly for RSS
    # Requires index on 'published' field
    rss_articles = query_couchdb(
        "articles", 
        selector={"published": {"$gt": None}}, 
        limit=limit, 
        sort=[{"published": "desc"}]
    )
    
    # Enrichment
    enrich_articles_with_events_and_trends(rss_articles)
    
    # Build RSS XML
    rss_items = []
    
    # Pre-fetch feed info for title mapping
    feeds = fetch_from_couchdb("feeds")
    feed_title_map = {feed.get("url"): feed.get("title") for feed in feeds if feed.get("url")}
    
    for article in rss_articles:
        item_xml = generate_rss_item_xml(article, feed_title_map, parse_datetime_safe)
        rss_items.append(item_xml)
    
    # Get current datetime for feed metadata
    build_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    
    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Moirai Aggregated Stream</title>
    <link>{request.host_url}</link>
    <description>Aggregated news stream with AI-synthesized Events and Trends</description>
    <language>en</language>
    <lastBuildDate>{build_date}</lastBuildDate>
    <atom:link href="{request.url}" rel="self" type="application/rss+xml" />

{chr(10).join(rss_items)}

  </channel>
</rss>"""
    
    return Response(rss_xml, mimetype='application/rss+xml')

@api_blueprint.route("/articles/<article_id>", methods=["DELETE"])
def delete_article(article_id):
    article = fetch_from_couchdb("articles", article_id)
    if not article:
        abort(404, description="Article not found")
        
    if delete_from_couchdb("articles", article_id, article["_rev"]):
        return jsonify({"status": "deleted"})
    else:
         abort(500, description="Failed to delete article")

# --- Events ---
@api_blueprint.route("/events", methods=["GET"])
def list_events():
    feed_url = request.args.get('feed_url')
    
    if feed_url:
        # 1. Get all article links for this feed
        articles = query_couchdb("articles", selector={"feed_url": feed_url}, fields=["link"], limit=10000)
        links = [a.get("link") for a in articles if a.get("link")]
        
        if not links:
            return jsonify([])
            
        # 2. Find events containing any of these links
        # Using $elemMatch with $in for efficient array searching
        selector = {
            "type": "event",
            "article_links": {"$elemMatch": {"$in": links}}
        }
        events = query_couchdb("events", selector=selector, limit=1000)
        return jsonify(events)
        
    events = fetch_from_couchdb("events")
    # Filter only actual events (legacy docs might not have 'type')
    events = [e for e in events if e.get('type', 'event') == 'event']
    return jsonify(events)

@api_blueprint.route("/events/<event_id>", methods=["DELETE"])
def delete_event(event_id):
    event = fetch_from_couchdb("events", event_id)
    if not event:
        abort(404)
    if delete_from_couchdb("events", event_id, event["_rev"]):
        return jsonify({"status": "deleted"})
    abort(500)

@api_blueprint.route("/events/<event_id>/links", methods=["DELETE"])
def remove_event_link(event_id):
    """Remove a specific article link from an event."""
    data = request.json
    link_to_remove = data.get("link")
    
    event = fetch_from_couchdb("events", event_id)
    if not event:
        abort(404)
        
    if "article_links" in event:
        event["article_links"] = [l for l in event["article_links"] if l != link_to_remove]
        if update_couchdb_doc("events", event_id, event):
            return jsonify(event)
            
    abort(500, description="Failed to update event")

# --- Trends ---
@api_blueprint.route("/trends", methods=["GET"])
def list_trends():
    feed_url = request.args.get('feed_url')
    
    if feed_url:
        # 1. Get all article links for this feed
        articles = query_couchdb("articles", selector={"feed_url": feed_url}, fields=["link"], limit=10000)
        links = [a.get("link") for a in articles if a.get("link")]
        
        if not links:
            return jsonify([])
            
        # 2. Find event IDs containing any of these links
        event_docs = query_couchdb("events", selector={"article_links": {"$elemMatch": {"$in": links}}}, fields=["_id"], limit=1000)
        event_ids = [e.get("_id") for e in event_docs if e.get("_id")]
        
        if not event_ids:
            return jsonify([])
            
        # 3. Find trends containing any of these event IDs
        selector = {
            "type": "trend",
            "event_ids": {"$elemMatch": {"$in": event_ids}}
        }
        trends = query_couchdb("trends", selector=selector, limit=1000)
        return jsonify(trends)

    trends = fetch_from_couchdb("trends")
    if not trends:
        trends = []
    # Ensure we only return trend documents
    trends = [t for t in trends if t.get('type', 'trend') == 'trend']
    return jsonify(trends)

@api_blueprint.route("/trends/<trend_id>", methods=["GET"])
def get_trend(trend_id):
    trend = fetch_from_couchdb("trends", trend_id)
    if not trend:
        abort(404, description="Trend not found")
    return jsonify(trend)

@api_blueprint.route("/trends/<trend_id>", methods=["DELETE"])
def delete_trend(trend_id):
    trend = fetch_from_couchdb("trends", trend_id)
    if not trend:
        abort(404)
    if delete_from_couchdb("trends", trend_id, trend["_rev"]):
        return jsonify({"status": "deleted"})
    abort(500)

@api_blueprint.route("/trends/<trend_id>/events", methods=["DELETE"])
def remove_trend_event(trend_id):
    """Remove a specific event ID from a trend."""
    data = request.json
    event_id_to_remove = data.get("event_id")
    
    trend = fetch_from_couchdb("trends", trend_id)
    if not trend:
        abort(404)
        
    if "event_ids" in trend:
        trend["event_ids"] = [eid for eid in trend["event_ids"] if eid != event_id_to_remove]
        if update_couchdb_doc("trends", trend_id, trend):
            return jsonify(trend)
            
    abort(500, description="Failed to update trend")

def fetch_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return {"url": url, "status": "success"}
        else:
            return {"url": url, "status": "failed", "code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"url": url, "status": "error", "message": str(e)}

# --- Config ---
@api_blueprint.route("/config", methods=["GET"])
def get_config():
    # Helper to return the effective config
    return jsonify({
        "allow_public_read": get_public_read_setting(),
        "iteration_interval": get_iteration_interval_setting(),
        "version": version.get_version_string()
    })

@api_blueprint.route("/config", methods=["PUT"])
def update_config():
    # Validate input
    try:
        validated = ConfigUpdateRequest(**request.json)
    except ValidationError as e:
        abort(400, description=str(e))
    
    # Fetch existing to get rev
    current_doc = get_config_doc()
    
    new_doc = {
        "_id": "main"
    }
    
    if current_doc:
        new_doc.update(current_doc)
        
    if validated.allow_public_read is not None:
        new_doc["allow_public_read"] = validated.allow_public_read
        
    if validated.iteration_interval is not None:
        new_doc["iteration_interval"] = validated.iteration_interval
        
    if update_couchdb_doc("config", "main", new_doc):
        return jsonify({"status": "updated", "config": new_doc})
    else:
        abort(500, description="Failed to update config")

# --- Stats ---

@api_blueprint.route("/stats", methods=["GET"])
@requires_auth
def get_stats():
    """Retrieve aggregation statistics from CouchDB MapReduce views."""
    from .db import query_couchdb_view
    
    try:
        # 1. Article Language Stats
        lang_rows = query_couchdb_view("articles", "stats", "by_language", group=True)
        lang_stats = {row["key"]: row["value"] for row in lang_rows}
        
        # 2. Feed Health Stats
        health_rows = query_couchdb_view("feeds", "health", "status", group=True)
        health_stats = {row["key"]: row["value"] for row in health_rows}
        
        return jsonify({
            "articles": {
                "by_language": lang_stats,
                "total": sum(lang_stats.values())
            },
            "feeds": {
                "health": health_stats,
                "total": sum(health_stats.values())
            }
        })
    except requests.exceptions.HTTPError as e:
        # CouchDB returned an HTTP error (401, 403, 5xx, etc.)
        abort(502, description=f"CouchDB error: {e.response.status_code}")
    except requests.exceptions.RequestException:
        # Network or connection error
        abort(503, description="Database unavailable")

# --- Search Endpoints ---

@api_blueprint.route("/articles/search", methods=["GET"])
@requires_auth
@limiter.limit("20 per minute")
def search_articles_endpoint():
    """Search articles by keyword with optional date filters"""
    query = request.args.get('q', '').strip()
    if not query:
        abort(400, description=ERROR_QUERY_REQUIRED)
    
    import re
    safe_query = re.escape(query)
    
    date_from = request.args.get('from', '')
    date_to = request.args.get('to', '')
    
    try:
        limit = int(request.args.get('limit', 50))
    except ValueError:
        abort(400, description=ERROR_LIMIT_INTEGER)
    
    if limit > 200:
        limit = 200
    
    # Build Mango selector for efficient querying
    selector = {
        "$or": [
            {"title": {"$regex": f"(?i){safe_query}"}},
            {"description": {"$regex": f"(?i){safe_query}"}},
            {"content": {"$regex": f"(?i){safe_query}"}}
        ]
    }
    
    # Add date range filters if provided
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from)
            selector["published"] = {"$gte": from_dt.isoformat()}
        except ValueError:
            return jsonify({"error": "Invalid date_from format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"}), 400
    
    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to)
            # Combine with existing published filter if from_dt exists
            if "published" in selector:
                selector["published"]["$lte"] = to_dt.isoformat()
            else:
                selector["published"] = {"$lte": to_dt.isoformat()}
        except ValueError:
            return jsonify({"error": "Invalid date_to format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"}), 400
    
    # Query CouchDB with selector
    articles = query_couchdb("articles", selector=selector, limit=limit)
    
    results = []
    for article in articles:
        results.append({
            "_id": article.get("_id"),
            "title": article.get("title", "Untitled"),
            "link": article.get("link", ""),
            "published": article.get("published", ""),
            "feed_title": article.get("feed_title", "Unknown"),
            "description": article.get("description", "")[:200]
        })
    
    return jsonify({
        "total": len(results),
        "query": query,
        "results": results
    })

@api_blueprint.route("/articles/recent", methods=["GET"])
@requires_auth
@limiter.limit("20 per minute")
def get_recent_articles_endpoint():
    """Get most recent articles"""
    try:
        hours = int(request.args.get('hours', 24))
        limit = int(request.args.get('limit', 50))
    except ValueError:
        abort(400, description="hours and limit must be integers")
    
    if hours > 168:  # Max 1 week
        hours = 168
    if limit > 200:
        limit = 200
    
    from datetime import timedelta
    
    # Calculate cutoff timestamp
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()
    
    # Use Mango query to filter at database level
    selector = {
        "published": {"$gte": cutoff_str}
    }
    
    # Query with sort by published date descending
    articles = query_couchdb(
        "articles",
        selector=selector,
        limit=limit * 2,  # Fetch extra to account for parsing issues
        sort=[{"published": "desc"}]
    )
    
    results = []
    for article in articles:
        pub_str = article.get("published", "")
        if pub_str:
            try:
                pub_dt = parse_datetime_safe(pub_str)
                # Double-check in case CouchDB string comparison differs from parsed date
                if pub_dt >= cutoff:
                    results.append({
                        "_id": article.get("_id"),
                        "title": article.get("title", "Untitled"),
                        "link": article.get("link", ""),
                        "published": pub_str,
                        "feed_title": article.get("feed_title", "Unknown"),
                        "description": article.get("description", "")[:200],
                        "_sort_date": pub_dt
                    })
            except (ValueError, AttributeError):
                # Skip articles with invalid/unparseable date formats rather than failing the entire request.
                # This allows the API to return valid articles even if some have malformed timestamps.
                pass
        
        if len(results) >= limit:
            break
    
    # Sort by published date descending (in case CouchDB sort isn't perfect)
    results.sort(key=lambda x: x.get("_sort_date", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    for r in results:
        r.pop("_sort_date", None)
    
    return jsonify({
        "total": len(results),
        "hours": hours,
        "results": results[:limit]
    })

@api_blueprint.route("/events/search", methods=["GET"])
@requires_auth
@limiter.limit("20 per minute")
def search_events_endpoint():
    """Search events by keyword using CouchDB query"""
    query = request.args.get('q', '').strip()
    if not query:
        abort(400, description=ERROR_QUERY_REQUIRED)
    
    import re
    safe_query = re.escape(query)
    
    try:
        limit = int(request.args.get('limit', 20))
    except ValueError:
        abort(400, description=ERROR_LIMIT_INTEGER)

    if limit > 100:
        limit = 100
    
    # Use Mango query with regex for case-insensitive search
    # Note: For better performance at scale, consider using a full-text search engine
    selector = {
        "$or": [
            {"name": {"$regex": f"(?i){safe_query}"}},
            {"description": {"$regex": f"(?i){safe_query}"}}
        ]
    }
    
    events = query_couchdb("events", selector=selector, limit=limit)
    
    results = []
    for event in events:
        results.append({
            "_id": event.get("_id"),
            "name": event.get("name", "Untitled"),
            "description": event.get("description", "")
        })
    
    return jsonify({
        "total": len(results),
        "query": query,
        "results": results
    })

@api_blueprint.route("/trends/search", methods=["GET"])
@requires_auth
@limiter.limit("20 per minute")
def search_trends_endpoint():
    """Search trends by keyword using CouchDB query"""
    query = request.args.get('q', '').strip()
    if not query:
        abort(400, description=ERROR_QUERY_REQUIRED)
    
    import re
    safe_query = re.escape(query)
    
    try:
        limit = int(request.args.get('limit', 20))
    except ValueError:
        abort(400, description=ERROR_LIMIT_INTEGER)

    if limit > 100:
        limit = 100
    
    # Use Mango query with regex for case-insensitive search
    # Note: For better performance at scale, consider using a full-text search engine
    selector = {
        "$or": [
            {"name": {"$regex": f"(?i){safe_query}"}},
            {"description": {"$regex": f"(?i){safe_query}"}}
        ]
    }
    
    trends = query_couchdb("trends", selector=selector, limit=limit)
    
    results = []
    for trend in trends:
        results.append({
            "_id": trend.get("_id"),
            "name": trend.get("name", "Untitled"),
            "description": trend.get("description", ""),
            "event_count": len(trend.get("event_ids", []))
        })
    
    return jsonify({
        "total": len(results),
        "query": query,
        "results": results
    })