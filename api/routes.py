from flask import Blueprint, jsonify, abort, request, Response
import os
import json
import version
import requests
import logging
from typing import Any
from datetime import datetime, timezone
from api.extensions import limiter, get_redis_client
from tasks.fetch_feed_task import FetchFeedTask
from tasks.favicon_fetcher import fetch_favicon_url
from tasks.scheduler_log import get_scheduler_logs
from api.db_config import get_couchdb_uri
from .db import (
    fetch_from_couchdb,
    delete_from_couchdb,
    update_couchdb_doc,
    query_couchdb,
)
from .auth import jwt_required, admin_required, verify_jwt_in_request
from pydantic import ValidationError
from .validation import FeedCreateRequest, FeedUpdateRequest, ConfigUpdateRequest
from .auth import get_auth_config

import uuid  # Import uuid

from api.enrichment import enrich_articles_with_issues, invalidate_feed_mappings_cache
from api.feed_ops import process_bulk_import_url
from api.rss_ops import generate_rss_item_xml
from api.article_ops import build_article_selector, paginate_results
from api.db_constants import (
    MONGO_REGEX,
    MONGO_OR,
    MONGO_GT,
    MONGO_GTE,
    MONGO_LTE,
)

api_blueprint = Blueprint("api", __name__)

# Configure logger
logger = logging.getLogger(__name__)

# Basic Auth Removed
# ADMIN_USERNAME / ADMIN_PASSWORD removed
ALLOW_PUBLIC_READ_ENV = os.environ.get("ALLOW_PUBLIC_READ", "false").lower() == "true"
ITERATION_INTERVAL_ENV = int(os.environ.get("ITERATION_INTERVAL", 600))

# Constants for error messages
ERROR_FEED_NOT_FOUND = "Feed not found"
ERROR_LIMIT_INTEGER = "limit must be an integer"
ERROR_QUERY_REQUIRED = "Query parameter 'q' is required"

# Mongo Constants are now imported from api.db_constants


def parse_datetime_safe(date_str):
    """Parse datetime and ensure it's timezone-aware for comparison."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        # If naive (no timezone), assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        # Return a very old date for invalid dates so they sort last
        return datetime.min.replace(tzinfo=timezone.utc)


# Auth helpers
def check_public_read_access():
    if get_public_read_setting():
        return True

    success, _ = verify_jwt_in_request()
    return success


def get_config_doc():
    """Helper to get the main config doc. Returns None if config doesn't exist or DB is unavailable."""
    return fetch_from_couchdb("config", "main")


def _fetch_json(url: str) -> dict[str, Any] | None:
    """Fetch JSON from a URL.

    Args:
        url: URL to fetch JSON from.

    Returns:
        Parsed JSON dict or None when unavailable.
    """
    try:
        response = requests.get(url, timeout=2)
        if response.ok:
            return response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Version lookup failed for %s: %s", url, exc)
    return None


def _derive_mcp_health_url(mcp_server_url: str) -> str:
    """Derive MCP health URL from the MCP server URL.

    Args:
        mcp_server_url: MCP server URL (typically the SSE endpoint).

    Returns:
        MCP health URL.
    """
    normalized = mcp_server_url.rstrip("/")
    if normalized.endswith("/health"):
        return normalized
    if normalized.endswith("/sse"):
        return f"{normalized.rsplit('/', 1)[0]}/health"
    return f"{normalized}/health"


def get_component_versions() -> dict[str, str]:
    """Collect versions for core components.

    Returns:
        Dictionary of component version strings.
    """
    versions: dict[str, str] = {
        "api": version.get_version_string(),
    }

    mcp_server_url = os.environ.get("MCP_SERVER_URL", "").strip()
    if mcp_server_url:
        health_url = _derive_mcp_health_url(mcp_server_url)
        payload = _fetch_json(health_url)
        if payload and isinstance(payload.get("version"), str):
            versions["mcp"] = payload["version"]
        else:
            versions["mcp"] = "unknown"

    couchdb_url = get_couchdb_uri()
    if couchdb_url:
        payload = _fetch_json(couchdb_url)
        if payload and isinstance(payload.get("version"), str):
            versions["couchdb"] = payload["version"]
        else:
            versions["couchdb"] = "unknown"

    return versions


def _extract_userspace(doc: dict[str, Any]) -> str | None:
    return doc.get("userspace") or doc.get("namespace")


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


def get_chat_export_verbose_setting() -> bool:
    """Checks DB for chat export verbosity setting, defaults to False."""
    config = get_config_doc()
    if config and "chat_export_verbose" in config:
        return bool(config["chat_export_verbose"])
    return False


@api_blueprint.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: *; connect-src 'self';"
    )
    return response


@api_blueprint.route("/health", methods=["GET"])
@limiter.exempt
def health_check():
    return jsonify({"status": "healthy"})


# Removed before_request_auth as we use explicit decorators now
# But we need to handle OPTIONS requests generally or via CORS ext
# api_blueprint.before_request ... (Skipping, existing logic was mainly for Basic Auth)


# --- Feeds ---
@api_blueprint.route("/feeds", methods=["POST"])
@admin_required
def create_feed():
    payload = request.json or {}
    raw_url = payload.get("url")
    if not raw_url or not str(raw_url).startswith(("http://", "https://")):
        abort(400, description="Only HTTP/HTTPS URLs are allowed")
    try:
        validated = FeedCreateRequest(**payload)
    except ValidationError as e:
        abort(400, description=str(e))

    feed_url = str(validated.url)

    # Check if feed with this URL already exists
    existing_feed = query_couchdb("feeds", selector={"original_url": feed_url}, limit=1)
    if existing_feed:
        abort(409, description="Feed with this URL already exists.")

    # Generate a GUID for the feed_id
    feed_id = str(uuid.uuid4())

    # Fetch favicon for the feed
    favicon_url = fetch_favicon_url(feed_url)

    feed_doc = {
        "_id": feed_id,
        "url": feed_url,  # Current URL, can change due to redirects
        "original_url": feed_url,  # Original URL, for uniqueness check and reference
        "title": validated.title,
        "category": validated.category or "general",
        "added_at": datetime.now(timezone.utc).isoformat(),
        "favicon_url": favicon_url,
    }

    if update_couchdb_doc("feeds", feed_id, feed_doc):
        # Invalidate feed mappings cache
        try:
            invalidate_feed_mappings_cache()
        except Exception as e:
            logger.error(f"Failed to invalidate feed mappings cache: {e}")
        return jsonify(feed_doc), 201
    else:
        abort(500, description="Failed to create feed")


@api_blueprint.route("/feeds", methods=["GET"])
@limiter.limit("10 per minute")
def list_feeds():
    if not check_public_read_access():
        response = jsonify({"message": "Unauthorized"})
        response.status_code = 401
        return response
    feeds = fetch_from_couchdb("feeds")
    return jsonify(feeds)


@api_blueprint.route("/feeds/<feed_id>", methods=["DELETE"])
@admin_required
def delete_feed(feed_id):
    feed = fetch_from_couchdb("feeds", feed_id)
    if not feed:
        abort(404, description=ERROR_FEED_NOT_FOUND)

    if delete_from_couchdb("feeds", feed_id, feed["_rev"]):
        # Invalidate feed mappings cache
        try:
            invalidate_feed_mappings_cache()
        except Exception as e:
            logger.error(f"Failed to invalidate feed mappings cache: {e}")
        return jsonify({"status": "deleted"})
    else:
        abort(500, description="Failed to delete feed")


@api_blueprint.route("/feeds/<feed_id>", methods=["PUT"])
@admin_required
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

    # If a new URL is provided (e.g., from a redirect), update it
    if validated.new_url:
        feed["url"] = str(validated.new_url)

    if update_couchdb_doc("feeds", feed_id, feed):
        # Invalidate feed mappings cache
        try:
            invalidate_feed_mappings_cache()
        except Exception as e:
            logger.error(f"Failed to invalidate feed mappings cache: {e}")
        return jsonify(feed)
    else:
        abort(500, description="Failed to update feed")


@api_blueprint.route("/feeds/refresh", methods=["POST"])
@admin_required
def refresh_feeds():
    """Triggers a background refresh of all registered feeds."""
    feeds = fetch_from_couchdb("feeds")
    if not feeds:
        return jsonify({"status": "no feeds found", "count": 0})

    count = 0
    for feed in feeds:
        feed_id = feed.get("_id")
        url = feed.get("url")
        original_url = feed.get("original_url")
        if feed_id and url and original_url:
            # Run in background thread (FetchFeedTask inherits from threading.Thread)
            task = FetchFeedTask(feed_id, url, original_url)
            task.start()
            count += 1

    return jsonify({"status": "started", "count": count})


@api_blueprint.route("/feeds/refresh/<path:feed_url>", methods=["POST"])
@admin_required
@limiter.limit("10 per minute")
def refresh_single_feed(feed_url):
    """Triggers a background refresh of a single feed by URL."""
    # Validate the feed exists efficiently
    selector = {"url": feed_url}
    existing_feeds = query_couchdb("feeds", selector=selector, limit=1)

    if not existing_feeds:
        # Also check original_url if not found by current url
        selector = {"original_url": feed_url}
        existing_feeds = query_couchdb("feeds", selector=selector, limit=1)
        if not existing_feeds:
            abort(404, description=ERROR_FEED_NOT_FOUND)

    feed = existing_feeds[0]
    feed_id = feed.get("_id")
    current_url = feed.get("url")
    original_url = feed.get("original_url")

    # Run in background thread
    task = FetchFeedTask(feed_id, current_url, original_url)
    task.start()

    return jsonify({"status": "started", "url": feed_url})


@api_blueprint.route("/feeds/bulk", methods=["POST"])
@admin_required
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
        abort(
            400,
            description=f"Too many URLs. Maximum {MAX_BULK_IMPORT_SIZE} URLs per request.",
        )

    results = {
        "total": len(urls),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
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


def _get_cached_articles_view(is_default_view):
    """Try to get default articles view from Redis."""
    if not is_default_view:
        return None
    try:
        redis_client = get_redis_client()
        if redis_client:
            cached_resp = redis_client.get("articles_default_json")
            if cached_resp:
                return Response(cached_resp, mimetype="application/json")
    except Exception as e:
        logger.error(f"Redis error in list_articles: {e}")
    return None


# --- Articles ---
@api_blueprint.route("/articles", methods=["GET"])
def list_articles():
    if not check_public_read_access():
        return jsonify({"message": "Unauthorized"}), 401

    # Pagination parameters
    try:
        limit = int(request.args.get("limit", 50))
        skip = int(request.args.get("skip", 0))
    except ValueError:
        abort(400, description="limit and skip must be integers")

    since = request.args.get("since")
    feed_id = request.args.get("feed_id")
    issue_id = request.args.get("issue_id")

    # Validate pagination params
    limit = min(max(limit, 1), 200)
    skip = max(skip, 0)

    # Caching
    is_default_view = (limit == 50 and skip == 0 and not since and not feed_id and not issue_id)
    cached = _get_cached_articles_view(is_default_view)
    if cached:
        return cached

    selector = build_article_selector(since, feed_id, issue_id)

    # If selector indicates no match (e.g., non-existent event/trend), return empty
    if selector.get("_id", {}).get("$eq") == "no_match":
        return jsonify({
            "articles": [],
            "total_count": 0,
            "has_more": False,
            "limit": limit,
            "skip": skip,
        })

    # Query CouchDB
    articles = query_couchdb(
        "articles",
        selector=selector,
        limit=limit + 1,
        skip=skip,
        sort=[{"published": "desc"}],
    )

    paginated_articles, has_more, total_count = paginate_results(articles, limit, skip)
    enrich_articles_with_issues(paginated_articles)

    response_data = {
        "articles": paginated_articles,
        "total_count": total_count,
        "has_more": has_more,
        "limit": limit,
        "skip": skip,
    }
    
    if is_default_view:
        _cache_articles_view(response_data)

    return jsonify(response_data)


def _cache_articles_view(response_data):
    """Store default view in Redis."""
    try:
        redis_client = get_redis_client()
        if redis_client:
            redis_client.setex("articles_default_json", 3600, json.dumps(response_data))
    except Exception as e:
        logger.error(f"Redis cache set error: {e}")


@api_blueprint.route("/stream.rss", methods=["GET"])
def rss_feed():
    """Generate RSS 2.0 feed for the aggregated article stream. Public endpoint (no auth required)."""
    if not check_public_read_access():
        response = jsonify({"message": "Unauthorized"})
        response.status_code = 401
        return response

    # Fetch all data (reuse logic from list_articles)
    limit = int(request.args.get("limit", 100))  # Default to 100 items for RSS
    limit = min(max(limit, 1), 500)  # Clamp between 1-500

    # Caching: Check Redis for default RSS feed
    is_default_view = (limit == 100)
    redis_client = None
    if is_default_view:
        try:
            redis_client = get_redis_client()
            if redis_client:
                cached_rss = redis_client.get("stream_rss_xml")
                if cached_rss:
                    return Response(cached_rss, mimetype="application/rss+xml")
        except Exception as e:
            logger.error(f"Redis error in rss_feed: {e}")

    # Query CouchDB directly for RSS
    # Requires index on 'published' field
    rss_articles = query_couchdb(
        "articles",
        selector={"published": {MONGO_GT: None}},
        limit=limit,
        sort=[{"published": "desc"}],
    )

    # Enrichment
    enrich_articles_with_issues(rss_articles)

    # Build RSS XML
    rss_items = []

    # Pre-fetch feed info for title mapping
    feeds = fetch_from_couchdb("feeds")
    feed_title_map = {
        feed.get("url"): feed.get("title") for feed in feeds if feed.get("url")
    }

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

    if is_default_view and redis_client:
        try:
            redis_client.setex("stream_rss_xml", 3600, rss_xml)
        except Exception as e:
            logger.error(f"Redis cache set error: {e}")

    return Response(rss_xml, mimetype="application/rss+xml")


@api_blueprint.route("/articles/<article_id>", methods=["DELETE"])
@admin_required
def delete_article(article_id):
    article = fetch_from_couchdb("articles", article_id)
    if not article:
        abort(404, description="Article not found")

    if delete_from_couchdb("articles", article_id, article["_rev"]):
        # Invalidate cache
        try:
            redis_client = get_redis_client()
            if redis_client:
                redis_client.delete("stream_rss_xml", "articles_default_json")
        except Exception as e:
            logger.error(f"Redis invalidation error: {e}")
        return jsonify({"status": "deleted"})
    else:
        abort(500, description="Failed to delete article")


def _resolve_feed_url(feed_filter):
    """Resolve feed filter to actual feed URL."""
    if feed_filter.startswith(("http://", "https://")):
        return feed_filter
    feed_doc = fetch_from_couchdb("feeds", feed_filter)
    return feed_doc.get("url") if feed_doc else feed_filter


def _filter_issues_by_feed(selector, resolved_feed_url):
    """Filter issues by feed URL and selector."""
    articles = query_couchdb(
        "articles", selector={"feed_url": resolved_feed_url}, fields=["link"], limit=10000
    )
    links = [a.get("link") for a in articles if a.get("link")]
    if not links:
        return []

    issues = query_couchdb("issues", selector=selector, limit=1000)
    link_set = set(links)
    return [
        issue for issue in issues
        if not (issue.get("premises") or [])
        or any((p or {}).get("id") in link_set for p in issue.get("premises", []))
    ]


def _filter_issues_by_selector(issues, longevity, status):
    """Filter issues by longevity and status."""
    if not (longevity or status):
        return issues
    return [
        i for i in issues
        if (not longevity or i.get("longevity") == longevity)
        and (not status or i.get("status") == status)
    ]


# --- Issues (Synthesized Resonances) ---
@api_blueprint.route("/issues", methods=["GET"])
def list_issues():
    if not check_public_read_access():
        response = jsonify({"message": "Unauthorized"})
        response.status_code = 401
        return response

    feed_filter = request.args.get("feed_url")
    longevity = request.args.get("longevity")  # transient, temporal, epic
    status = request.args.get("status")  # active, eternal

    selector = {}
    if longevity:
        selector["longevity"] = longevity
    if status:
        selector["status"] = status

    if feed_filter:
        resolved_feed_url = _resolve_feed_url(feed_filter)
        filtered_issues = _filter_issues_by_feed(selector, resolved_feed_url)
        return jsonify(filtered_issues)

    issues = fetch_from_couchdb("issues")
    issues = _filter_issues_by_selector(issues, longevity, status)
    return jsonify(issues)


@api_blueprint.route("/issues/<issue_id>", methods=["GET"])
def get_issue(issue_id):
    issue = fetch_from_couchdb("issues", issue_id)
    if not issue:
        abort(404, description="Issue not found")
    return jsonify(issue)


@api_blueprint.route("/issues/<issue_id>", methods=["DELETE"])
@admin_required
def delete_issue(issue_id):
    issue = fetch_from_couchdb("issues", issue_id)
    if not issue:
        abort(404)
    if delete_from_couchdb("issues", issue_id, issue["_rev"]):
        return jsonify({"status": "deleted"})
    abort(500)


@api_blueprint.route("/issues/<issue_id>/premises", methods=["DELETE"])
@admin_required
def remove_issue_premise(issue_id):
    """Remove a specific premise (link or nested issue) from an issue."""
    data = request.json
    premise_id = data.get("id")

    issue = fetch_from_couchdb("issues", issue_id)
    if not issue:
        abort(404)

    if "premises" in issue:
        issue["premises"] = [
            p for p in issue["premises"] if p.get("id") != premise_id
        ]
        if update_couchdb_doc("issues", issue_id, issue):
            return jsonify(issue)

    abort(500, description="Failed to update issue")


def fetch_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return {"url": url, "status": "success"}
        else:
            return {"url": url, "status": "failed", "code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"url": url, "status": "error", "message": str(e)}


# --- Config ---
@api_blueprint.route("/config", methods=["GET"])
@admin_required
def get_config():
    # Helper to return the effective config
    return jsonify(
        {
            "allow_public_read": get_public_read_setting(),
            "chat_export_verbose": get_chat_export_verbose_setting(),
            "iteration_interval": get_iteration_interval_setting(),
            "version": version.get_version_string(),
            "components": get_component_versions(),
            "default_llm_provider": os.environ.get("DEFAULT_LLM_PROVIDER", "ollama"),
            "default_model_name": os.environ.get("MODEL_NAME", "llama3.1"),
            # Include public auth config
            **get_auth_config(),
        }
    )


@api_blueprint.route("/config", methods=["PUT"])
@admin_required
def update_config():
    # Validate input
    try:
        validated = ConfigUpdateRequest(**request.json)
    except ValidationError as e:
        abort(400, description=str(e))

    # Fetch existing to get rev
    current_doc = get_config_doc()

    new_doc = {"_id": "main"}

    if current_doc:
        new_doc.update(current_doc)

    if validated.allow_public_read is not None:
        new_doc["allow_public_read"] = validated.allow_public_read

    if validated.chat_export_verbose is not None:
        new_doc["chat_export_verbose"] = validated.chat_export_verbose

    if validated.iteration_interval is not None:
        new_doc["iteration_interval"] = validated.iteration_interval

    # Handle extra fields that might not be in ConfigUpdateRequest strict model yet
    # We can allow dynamic fields for now or update the model.
    # Let's assume request.json has them if passed.

    if "google_client_id" in request.json:
        new_doc["google_client_id"] = request.json["google_client_id"]

    if "entra_client_id" in request.json:
        new_doc["entra_client_id"] = request.json["entra_client_id"]

    if "entra_tenant_id" in request.json:
        new_doc["entra_tenant_id"] = request.json["entra_tenant_id"]

    if "github_client_id" in request.json:
        new_doc["github_client_id"] = request.json["github_client_id"]

    if "github_client_secret" in request.json:
        new_doc["github_client_secret"] = request.json["github_client_secret"]

    if update_couchdb_doc("config", "main", new_doc):
        return jsonify({"status": "updated", "config": new_doc})
    else:
        abort(500, description="Failed to update config")


@api_blueprint.route("/scheduler/logs", methods=["GET"])
@admin_required
def list_scheduler_logs():
    logs = get_scheduler_logs()
    limit = request.args.get("limit")
    if limit:
        try:
            limit_value = int(limit)
        except ValueError:
            abort(400, description="Invalid limit")
        if limit_value > 0:
            logs = logs[-limit_value:]
    return jsonify({"logs": logs})


@api_blueprint.route("/userspaces", methods=["GET"])
@admin_required
def list_userspaces():
    userspaces = set()
    for doc in (fetch_from_couchdb("issues") or []):
        value = _extract_userspace(doc)
        if value:
            userspaces.add(value)
    for doc in (fetch_from_couchdb("feeds") or []):
        value = _extract_userspace(doc)
        if value:
            userspaces.add(value)
    return jsonify(sorted(userspaces))


# --- Stats ---


@api_blueprint.route("/stats", methods=["GET"])
@jwt_required
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

        return jsonify(
            {
                "articles": {
                    "by_language": lang_stats,
                    "total": sum(lang_stats.values()),
                },
                "feeds": {"health": health_stats, "total": sum(health_stats.values())},
            }
        )
    except requests.exceptions.HTTPError as e:
        # CouchDB returned an HTTP error (401, 403, 5xx, etc.)
        # Log detailed error internally but return user-friendly message
        # Truncate response text to avoid excessive logging
        response_preview = e.response.text[:200] if e.response.text else ""
        logger.error(
            f"CouchDB HTTP error in /stats: {e.response.status_code} {response_preview}"
        )

        # Return appropriate message based on error type
        if 400 <= e.response.status_code < 500:
            abort(502, description="Unable to retrieve statistics")
        else:
            abort(502, description="Statistics temporarily unavailable")
    except requests.exceptions.RequestException as e:
        # Network or connection error
        logger.error(f"CouchDB connection error in /stats: {e}")
        abort(503, description="Database unavailable")

    # Fallback return to avoid implicit None; should be unreachable
    return jsonify(
        {
            "articles": {"by_language": {}, "total": 0},
            "feeds": {"health": {}, "total": 0},
        }
    )


# --- Search Endpoints ---


@api_blueprint.route("/articles/search", methods=["GET"])
@jwt_required
@limiter.limit("20 per minute")
def search_articles_endpoint():
    """Search articles by keyword with optional date filters"""
    query = request.args.get("q", "").strip()
    if not query:
        abort(400, description=ERROR_QUERY_REQUIRED)

    import re

    safe_query = re.escape(query)

    date_from = request.args.get("from", "")
    date_to = request.args.get("to", "")

    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        abort(400, description=ERROR_LIMIT_INTEGER)

    if limit > 200:
        limit = 200

    # Build Mango selector for efficient querying
    selector = {
        MONGO_OR: [
            {"title": {MONGO_REGEX: f"(?i){safe_query}"}},
            {"description": {MONGO_REGEX: f"(?i){safe_query}"}},
            {"content": {MONGO_REGEX: f"(?i){safe_query}"}},
        ]
    }

    # Add date range filters if provided
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from)
            selector["published"] = {MONGO_GTE: from_dt.isoformat()}
        except ValueError:
            return jsonify(
                {
                    "error": "Invalid date_from format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
                }
            ), 400

    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to)
            # Combine with existing published filter if from_dt exists
            if "published" in selector:
                selector["published"][MONGO_LTE] = to_dt.isoformat()
            else:
                selector["published"] = {MONGO_LTE: to_dt.isoformat()}
        except ValueError:
            return jsonify(
                {
                    "error": "Invalid date_to format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
                }
            ), 400

    # Query CouchDB with selector
    articles = query_couchdb("articles", selector=selector, limit=limit)

    results = []
    for article in articles:
        results.append(
            {
                "_id": article.get("_id"),
                "title": article.get("title", "Untitled"),
                "link": article.get("link", ""),
                "published": article.get("published", ""),
                "feed_url": article.get("feed_url", ""),
                "feed_title": article.get("feed_title", "Unknown"),
                "description": article.get("description", "")[:200],
            }
        )

    return jsonify({"total": len(results), "query": query, "results": results})


@api_blueprint.route("/articles/recent", methods=["GET"])
@jwt_required
@limiter.limit("20 per minute")
def get_recent_articles_endpoint():
    """Get most recent articles"""
    try:
        hours = int(request.args.get("hours", 24))
        limit = int(request.args.get("limit", 50))
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
    selector = {"published": {MONGO_GTE: cutoff_str}}

    # Query with sort by published date descending
    articles = query_couchdb(
        "articles",
        selector=selector,
        limit=limit * 2,  # Fetch extra to account for parsing issues
        sort=[{"published": "desc"}],
    )

    results = []
    for article in articles:
        pub_str = article.get("published", "")
        if pub_str:
            try:
                pub_dt = parse_datetime_safe(pub_str)
                # Double-check in case CouchDB string comparison differs from parsed date
                if pub_dt >= cutoff:
                    results.append(
                        {
                            "_id": article.get("_id"),
                            "title": article.get("title", "Untitled"),
                            "link": article.get("link", ""),
                            "published": pub_str,
                            "feed_title": article.get("feed_title", "Unknown"),
                            "description": article.get("description", "")[:200],
                            "_sort_date": pub_dt,
                        }
                    )
            except (ValueError, AttributeError):
                # Skip articles with invalid/unparseable date formats rather than failing the entire request.
                # This allows the API to return valid articles even if some have malformed timestamps.
                pass

        if len(results) >= limit:
            break

    # Sort by published date descending (in case CouchDB sort isn't perfect)
    results.sort(
        key=lambda x: x.get("_sort_date", datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    for r in results:
        r.pop("_sort_date", None)

    return jsonify({"total": len(results), "hours": hours, "results": results[:limit]})


@api_blueprint.route("/issues/search", methods=["GET"])
@jwt_required
@limiter.limit("20 per minute")
def search_issues_endpoint():
    """Search issues by keyword using CouchDB query"""
    query = request.args.get("q", "").strip()
    if not query:
        abort(400, description=ERROR_QUERY_REQUIRED)

    import re

    safe_query = re.escape(query)

    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        abort(400, description=ERROR_LIMIT_INTEGER)

    if limit > 100:
        limit = 100

    # Use Mango query with regex for case-insensitive search
    selector = {
        "$or": [
            {"logos": {"$regex": f"(?i){safe_query}"}},
            {"description": {"$regex": f"(?i){safe_query}"}},
        ]
    }

    issues = query_couchdb("issues", selector=selector, limit=limit)

    results = []
    for issue in issues:
        results.append(
            {
                "_id": issue.get("_id"),
                "logos": issue.get("logos", "Untitled"),
                "description": issue.get("description", ""),
                "longevity": issue.get("longevity", "transient"),
                "status": issue.get("status", "active"),
                "premise_count": len(issue.get("premises", [])),
            }
        )

    return jsonify({"total": len(results), "query": query, "results": results})
