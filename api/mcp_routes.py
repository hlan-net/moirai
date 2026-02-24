from flask import Blueprint, jsonify, request, abort
from datetime import datetime, timezone
import hashlib
import json
from api.db import fetch_from_couchdb, store_to_couchdb, query_couchdb
from api.enrichment import enrich_issues_with_constituents
from api.validation import (
    EventCreateRequest,
    TrendCreateRequest,
    validate_userspace_param,
)
from pydantic import ValidationError

mcp_blueprint = Blueprint("mcp", __name__)

# Constants for repeated literals
ERROR_USERSPACE_REQUIRED = "'userspace' query parameter is required"
ERROR_EVENT_NOT_FOUND = "Event not found"
ERROR_TREND_NOT_FOUND = "Trend not found"


def _normalize_event_payload(payload):
    normalized = dict(payload or {})
    if "name" in normalized and "title" not in normalized:
        normalized["title"] = normalized["name"]
    if "article_ids" in normalized and "article_links" not in normalized:
        normalized["article_links"] = normalized["article_ids"]
    return normalized


def _normalize_trend_payload(payload):
    normalized = dict(payload or {})
    if "name" in normalized and "title" not in normalized:
        normalized["title"] = normalized["name"]
    return normalized


def _userspace_selector(userspace):
    return {"$or": [{"userspace": userspace}, {"namespace": userspace}]}


def _extract_userspace(doc):
    return doc.get("userspace") or doc.get("namespace")


def _issue_doc_from_event(validated):
    premises = [{"type": "message", "id": link} for link in validated.article_links]
    event_doc = {
        "type": "issue",
        "logos": validated.title,
        "description": validated.description,
        "premises": premises,
        "longevity": "transient",
        "status": "active",
        "born_at": datetime.now(timezone.utc).isoformat(),
        "passed_at": None,
        "userspace": validated.userspace,
    }
    return event_doc


def _issue_doc_from_trend(validated):
    premises = [{"type": "issue", "id": eid} for eid in validated.event_ids]
    trend_doc = {
        "type": "issue",
        "logos": validated.title,
        "description": validated.description,
        "premises": premises,
        "longevity": "temporal",
        "status": "active",
        "born_at": datetime.now(timezone.utc).isoformat(),
        "passed_at": None,
        "userspace": validated.userspace,
    }
    return trend_doc


def _extract_article_ids(issue):
    article_ids = []
    seen = set()
    for premise in issue.get("premises", []):
        if premise.get("type") == "message":
            link = premise.get("id")
            if link and link not in seen:
                seen.add(link)
                article_ids.append(link)
    if isinstance(issue.get("article_links"), list):
        for link in issue["article_links"]:
            if link and link not in seen:
                seen.add(link)
                article_ids.append(link)
    return article_ids


def _extract_event_ids(issue):
    event_ids = []
    seen = set()
    for premise in issue.get("premises", []):
        if premise.get("type") == "issue":
            issue_id = premise.get("id")
            if issue_id and issue_id not in seen:
                seen.add(issue_id)
                event_ids.append(issue_id)
    if isinstance(issue.get("event_ids"), list):
        for issue_id in issue["event_ids"]:
            if issue_id and issue_id not in seen:
                seen.add(issue_id)
                event_ids.append(issue_id)
    return event_ids


def _event_payload_from_issue(issue):
    payload = dict(issue)
    payload["name"] = issue.get("logos") or issue.get("name")
    payload["article_ids"] = _extract_article_ids(issue)
    return payload


def _trend_payload_from_issue(issue):
    payload = dict(issue)
    payload["name"] = issue.get("logos") or issue.get("name")
    payload["event_ids"] = _extract_event_ids(issue)
    return payload

# Articles Endpoints


@mcp_blueprint.route("/articles", methods=["GET"])
def retrieve_articles():
    """
    Retrieve articles with optional filtering by date.
    Query Parameters:
        - since: ISO 8601 timestamp to retrieve articles published after a certain date
    """
    articles = fetch_from_couchdb("articles")

    # Filter by 'since' parameter if provided
    since = request.args.get("since")
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            filtered_articles = []
            for article in articles:
                if "published" in article:
                    try:
                        article_dt = datetime.fromisoformat(
                            article["published"].replace("Z", "+00:00")
                        )
                        if article_dt >= since_dt:
                            filtered_articles.append(article)
                    except (ValueError, AttributeError):
                        # Skip articles with invalid date format
                        continue
            articles = filtered_articles
        except ValueError:
            abort(400, description="Invalid 'since' parameter. Use ISO 8601 format.")

    return jsonify(articles)


# Events Endpoints


@mcp_blueprint.route("/events", methods=["POST"])
def create_event():
    """
    Create a new event and link it to articles.
    Request Body:
        - name: Event name
        - description: Event description
        - article_ids: List of article IDs to link to this event
        - userspace: Userspace GUID (required)
    """
    payload = _normalize_event_payload(request.get_json() or {})
    try:
        validated = EventCreateRequest(**payload)
    except ValidationError as e:
        abort(400, description=str(e))

    if not validated.userspace:
        abort(400, description="'userspace' is required")

    try:
        validate_userspace_param(validated.userspace)
    except ValueError as e:
        abort(400, description=str(e))

    event_doc = _issue_doc_from_event(validated)

    hash_payload = {
        "title": validated.title,
        "description": validated.description,
        "article_links": validated.article_links,
    }
    event_hash = hashlib.sha256(
        json.dumps(hash_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    event_doc["_id"] = event_hash

    result = store_to_couchdb("issues", event_doc)

    return jsonify({"status": "success", "event_id": result.get("id", event_hash)}), 201


@mcp_blueprint.route("/events", methods=["GET"])
def list_events():
    """
    Retrieve a list of all events.
    """
    userspace = request.args.get("userspace")
    if not userspace:
        abort(400, description=ERROR_USERSPACE_REQUIRED)
    try:
        validate_userspace_param(userspace)
    except ValueError as e:
        abort(400, description=str(e))

    selector = {
        "type": "issue",
        "longevity": "transient",
        **_userspace_selector(userspace),
    }
    issues = query_couchdb("issues", selector=selector)
    events = [_event_payload_from_issue(issue) for issue in issues]
    return jsonify(events)


@mcp_blueprint.route("/events/<event_id>", methods=["GET"])
def get_event(event_id):
    """
    Retrieve a single event by ID.
    Query Parameters:
        - include_articles: Boolean to include full article objects
        - userspace: Userspace GUID (required)
    """
    userspace = request.args.get("userspace")
    if not userspace:
        abort(400, description=ERROR_USERSPACE_REQUIRED)
    try:
        validate_userspace_param(userspace)
    except ValueError as e:
        abort(400, description=str(e))

    event = fetch_from_couchdb("issues", event_id)
    if not event:
        abort(404, description=ERROR_EVENT_NOT_FOUND)

    if event.get("type") != "issue" or event.get("longevity") != "transient":
        abort(404, description=ERROR_EVENT_NOT_FOUND)

    if _extract_userspace(event) != userspace:
        abort(404, description=ERROR_EVENT_NOT_FOUND)

    # Check if we should include full article objects
    include_articles = request.args.get("include_articles", "").lower() == "true"

    if include_articles:
        enrich_issues_with_constituents([event], recursive=True)

    return jsonify(_event_payload_from_issue(event))


# Trends Endpoints


@mcp_blueprint.route("/trends", methods=["POST"])
def create_trend():
    """
    Create a new trend and link it to events.
    Request Body:
        - name: Trend name
        - description: Trend description
        - event_ids: List of event IDs to link to this trend
        - userspace: Userspace GUID (required)
    """
    payload = _normalize_trend_payload(request.get_json() or {})
    try:
        validated = TrendCreateRequest(**payload)
    except ValidationError as e:
        abort(400, description=str(e))

    if not validated.userspace:
        abort(400, description="'userspace' is required")

    try:
        validate_userspace_param(validated.userspace)
    except ValueError as e:
        abort(400, description=str(e))

    trend_doc = _issue_doc_from_trend(validated)

    hash_payload = {
        "title": validated.title,
        "description": validated.description,
        "event_ids": validated.event_ids,
    }
    trend_hash = hashlib.sha256(
        json.dumps(hash_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    trend_doc["_id"] = trend_hash

    result = store_to_couchdb("issues", trend_doc)

    return jsonify({"status": "success", "trend_id": result.get("id", trend_hash)}), 201


@mcp_blueprint.route("/trends", methods=["GET"])
def list_trends():
    """
    Retrieve a list of all trends.
    """
    userspace = request.args.get("userspace")
    if not userspace:
        abort(400, description=ERROR_USERSPACE_REQUIRED)
    try:
        validate_userspace_param(userspace)
    except ValueError as e:
        abort(400, description=str(e))

    selector = {
        "type": "issue",
        "longevity": "temporal",
        **_userspace_selector(userspace),
    }
    issues = query_couchdb("issues", selector=selector)
    trends = [_trend_payload_from_issue(issue) for issue in issues]
    return jsonify(trends)


@mcp_blueprint.route("/trends/<trend_id>", methods=["GET"])
def get_trend(trend_id):
    """
    Retrieve a single trend by ID.
    Query Parameters:
        - include_events: Boolean to include full event objects
        - include_articles: Boolean to include full article objects linked to events
        - userspace: Userspace GUID (required)
    """
    userspace = request.args.get("userspace")
    if not userspace:
        abort(400, description=ERROR_USERSPACE_REQUIRED)
    try:
        validate_userspace_param(userspace)
    except ValueError as e:
        abort(400, description=str(e))

    trend = fetch_from_couchdb("issues", trend_id)
    if not trend:
        abort(404, description=ERROR_TREND_NOT_FOUND)

    if trend.get("type") != "issue" or trend.get("longevity") != "temporal":
        abort(404, description=ERROR_TREND_NOT_FOUND)

    if _extract_userspace(trend) != userspace:
        abort(404, description=ERROR_TREND_NOT_FOUND)

    # Check if we should include full event objects
    include_events = request.args.get("include_events", "").lower() == "true"
    if include_events:
        enrich_issues_with_constituents([trend], recursive=True)

    return jsonify(_trend_payload_from_issue(trend))
