from flask import Blueprint, jsonify, request, abort
import os
import requests
import urllib.parse
import sys
import re
from datetime import datetime
import hashlib
import json

mcp_blueprint = Blueprint('mcp', __name__)

COUCHDB_URI = os.environ.get("COUCHDB_URI", "http://localhost:5984/")

def fetch_from_couchdb(db_name, doc_id=None):
    """Fetches data from CouchDB. If doc_id is None, lists all documents in the database."""
    allowed_dbs = {"feeds", "articles", "events", "trends"}
    if db_name not in allowed_dbs:
        abort(400, description="Invalid database name.")
    if doc_id and not re.match(r'^[A-Za-z0-9\-_]+$', doc_id):
        abort(400, description="Invalid document id.")
    try:
        if doc_id:
            safe_db_name = urllib.parse.quote(db_name, safe="")
            safe_doc_id = urllib.parse.quote(doc_id, safe="")
            response = requests.get(f"{COUCHDB_URI}{safe_db_name}/{safe_doc_id}")
        else:
            response = requests.get(f"{COUCHDB_URI}{db_name}/_all_docs", params={"include_docs": "true"})

        response.raise_for_status()
        if doc_id:
            return response.json()
        else:
            docs = [row["doc"] for row in response.json()["rows"]]
            return docs
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from CouchDB: {e}")
        abort(500, description="Database error")
    except Exception as e:
        print(f"Unexpected error: {e}")
        abort(500, description="Unexpected error")

def store_to_couchdb(db_name, doc):
    """Stores a document to CouchDB."""
    allowed_dbs = {"feeds", "articles", "events", "trends"}
    if db_name not in allowed_dbs:
        abort(400, description="Invalid database name.")
    
    try:
        safe_db_name = urllib.parse.quote(db_name, safe="")
        response = requests.post(f"{COUCHDB_URI}{safe_db_name}", json=doc)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error storing to CouchDB: {e}")
        abort(500, description="Database error")
    except Exception as e:
        print(f"Unexpected error: {e}")
        abort(500, description="Unexpected error")

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
    since = request.args.get('since')
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            filtered_articles = []
            for article in articles:
                if 'published' in article:
                    try:
                        article_dt = datetime.fromisoformat(article['published'].replace('Z', '+00:00'))
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
    
    if 'name' not in data or 'description' not in data:
        abort(400, description="'name' and 'description' are required fields")
    
    if 'article_ids' not in data or not isinstance(data['article_ids'], list):
        abort(400, description="'article_ids' must be a list")
    
    # Create event document
    event_doc = {
        "name": data['name'],
        "description": data['description'],
        "article_ids": data['article_ids']
    }
    
    # Generate a unique ID based on the content
    event_hash = hashlib.sha256(json.dumps(event_doc, sort_keys=True).encode('utf-8')).hexdigest()
    event_doc['_id'] = event_hash
    
    # Store the event
    result = store_to_couchdb("events", event_doc)
    
    return jsonify({
        "status": "success",
        "event_id": result.get('id', event_hash)
    }), 201

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
    include_articles = request.args.get('include_articles', '').lower() == 'true'
    
    if include_articles and 'article_ids' in event:
        articles = []
        for article_id in event['article_ids']:
            try:
                article = fetch_from_couchdb("articles", article_id)
                if article:
                    articles.append(article)
            except Exception as e:
                # Skip articles that don't exist or can't be fetched
                print(f"Warning: Could not fetch article {article_id}: {e}")
                continue
        event['articles'] = articles
    
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
    
    if 'name' not in data or 'description' not in data:
        abort(400, description="'name' and 'description' are required fields")
    
    if 'event_ids' not in data or not isinstance(data['event_ids'], list):
        abort(400, description="'event_ids' must be a list")
    
    # Create trend document
    trend_doc = {
        "name": data['name'],
        "description": data['description'],
        "event_ids": data['event_ids']
    }
    
    # Generate a unique ID based on the content
    trend_hash = hashlib.sha256(json.dumps(trend_doc, sort_keys=True).encode('utf-8')).hexdigest()
    trend_doc['_id'] = trend_hash
    
    # Store the trend
    result = store_to_couchdb("trends", trend_doc)
    
    return jsonify({
        "status": "success",
        "trend_id": result.get('id', trend_hash)
    }), 201

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
    include_events = request.args.get('include_events', '').lower() == 'true'
    include_articles = request.args.get('include_articles', '').lower() == 'true'
    
    if include_events and 'event_ids' in trend:
        events = []
        for event_id in trend['event_ids']:
            try:
                event = fetch_from_couchdb("events", event_id)
                if event:
                    # If include_articles is also requested, fetch articles for each event
                    if include_articles and 'article_ids' in event:
                        articles = []
                        for article_id in event['article_ids']:
                            try:
                                article = fetch_from_couchdb("articles", article_id)
                                if article:
                                    articles.append(article)
                            except Exception as e:
                                print(f"Warning: Could not fetch article {article_id}: {e}")
                                continue
                        event['articles'] = articles
                    events.append(event)
            except Exception as e:
                # Skip events that don't exist or can't be fetched
                print(f"Warning: Could not fetch event {event_id}: {e}")
                continue
        trend['events'] = events
    
    return jsonify(trend)
