from flask import Blueprint, jsonify, request, abort
from datetime import datetime
import hashlib
import json
from api.db import fetch_from_couchdb, store_to_couchdb, delete_from_couchdb
from api.enrichment import enrich_issues_with_constituents

mcp_blueprint = Blueprint("mcp", __name__)

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
    """
    data = request.get_json()

    if not data:
        abort(400, description="Request body is required")

    if "name" not in data or "description" not in data:
        abort(400, description="'name' and 'description' are required fields")

    if "article_ids" not in data or not isinstance(data["article_ids"], list):
        abort(400, description="'article_ids' must be a list")

    # Create event document
    event_doc = {
        "name": data["name"],
        "description": data["description"],
        "article_ids": data["article_ids"],
    }

    # Generate a unique ID based on the content
    event_hash = hashlib.sha256(
        json.dumps(event_doc, sort_keys=True).encode("utf-8")
    ).hexdigest()
    event_doc["_id"] = event_hash

    # Store the event
    result = store_to_couchdb("events", event_doc)

    return jsonify({"status": "success", "event_id": result.get("id", event_hash)}), 201


@mcp_blueprint.route("/events", methods=["GET"])
def list_events():
    """
    Retrieve a list of all events.
    """
    events = fetch_from_couchdb("events")
    return jsonify(events)


@mcp_blueprint.route("/events/<event_id>", methods=["GET"])
def get_event(event_id):
    """
    Retrieve a single event by ID.
    Query Parameters:
        - include_articles: Boolean to include full article objects
    """

    event = fetch_from_couchdb("events", event_id)
    if not event:
        abort(404, description="Event not found")

    # Check if we should include full article objects
    include_articles = request.args.get("include_articles", "").lower() == "true"

    if include_articles:
        enrich_issues_with_constituents([event], recursive=True)

    return jsonify(event)


# Trends Endpoints


@mcp_blueprint.route("/trends", methods=["POST"])
def create_trend():
    """
    Create a new trend and link it to events.
    Request Body:
        - name: Trend name
        - description: Trend description
        - event_ids: List of event IDs to link to this trend
    """
    data = request.get_json()

    if not data:
        abort(400, description="Request body is required")

    if "name" not in data or "description" not in data:
        abort(400, description="'name' and 'description' are required fields")

    if "event_ids" not in data or not isinstance(data["event_ids"], list):
        abort(400, description="'event_ids' must be a list")

    # Create trend document
    trend_doc = {
        "name": data["name"],
        "description": data["description"],
        "event_ids": data["event_ids"],
    }

    # Generate a unique ID based on the content
    trend_hash = hashlib.sha256(
        json.dumps(trend_doc, sort_keys=True).encode("utf-8")
    ).hexdigest()
    trend_doc["_id"] = trend_hash

    # Store the trend
    result = store_to_couchdb("trends", trend_doc)

    return jsonify({"status": "success", "trend_id": result.get("id", trend_hash)}), 201


@mcp_blueprint.route("/trends", methods=["GET"])
def list_trends():
    """
    Retrieve a list of all trends.
    """
    trends = fetch_from_couchdb("trends")
    return jsonify(trends)


@mcp_blueprint.route("/trends/<trend_id>", methods=["GET"])
def get_trend(trend_id):
    """
    Retrieve a single trend by ID.
    Query Parameters:
        - include_events: Boolean to include full event objects
        - include_articles: Boolean to include full article objects linked to events
    """
    trend = fetch_from_couchdb("trends", trend_id)
    if not trend:
        abort(404, description="Trend not found")

    # Check if we should include full event objects
    include_events = request.args.get("include_events", "").lower() == "true"
    include_articles = request.args.get("include_articles", "").lower() == "true"

    if include_events:
        enrich_issues_with_constituents([trend], recursive=True)

    return jsonify(trend)
