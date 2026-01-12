from flask import Blueprint, jsonify, abort, request, Response
import os
from functools import wraps
from tasks.fetch_feed_task import FetchFeedTask
from .db import fetch_from_couchdb, delete_from_couchdb, update_couchdb_doc
from pydantic import ValidationError
from .validation import (
    FeedCreateRequest, FeedUpdateRequest,
    EventCreateRequest, EventUpdateRequest,
    TrendCreateRequest, TrendUpdateRequest,
    ConfigUpdateRequest,
    validate_namespace_param
)

api_blueprint = Blueprint('api', __name__)

API_USERNAME = os.environ.get("API_USERNAME")
API_PASSWORD = os.environ.get("API_PASSWORD")
ALLOW_PUBLIC_READ_ENV = os.environ.get("ALLOW_PUBLIC_READ", "false").lower() == "true"
ITERATION_INTERVAL_ENV = int(os.environ.get("ITERATION_INTERVAL", 600))

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
    """Helper to get the main config doc."""
    try:
        return fetch_from_couchdb("config", "main")
    except Exception:
        return None

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

# Apply auth to all routes in this blueprint
@api_blueprint.before_request
def before_request_auth():
    if request.method == "OPTIONS":
        return # Allow CORS preflight if needed
    
    # Optional public read access for articles and feeds only
    if request.method == "GET" and request.endpoint in ["api.list_articles", "api.list_feeds"]:
         if get_public_read_setting():
             return None

    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

# --- Feeds ---
@api_blueprint.route("/feeds", methods=["GET"])
def list_feeds():
    feeds = fetch_from_couchdb("feeds")
    return jsonify(feeds)

@api_blueprint.route("/feeds/<feed_id>", methods=["DELETE"])
def delete_feed(feed_id):
    feed = fetch_from_couchdb("feeds", feed_id)
    if not feed:
        abort(404, description="Feed not found")
    
    if delete_from_couchdb("feeds", feed_id, feed["_rev"]):
        return jsonify({"status": "deleted"})
    else:
        abort(500, description="Failed to delete feed")

@api_blueprint.route("/feeds/<feed_id>", methods=["PUT"])
def update_feed(feed_id):
    feed = fetch_from_couchdb("feeds", feed_id)
    if not feed:
        abort(404, description="Feed not found")
    
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

# --- Articles ---
@api_blueprint.route("/articles", methods=["GET"])
def list_articles():
    feeds = fetch_from_couchdb("feeds")
    articles = fetch_from_couchdb("articles")
    events = fetch_from_couchdb("events")
    
    feed_title_map = {feed.get("url"): feed.get("title") for feed in feeds if feed.get("url")}
    
    article_event_map = {}
    for event in events:
        for link in event.get("article_links", []):
            if link not in article_event_map:
                article_event_map[link] = []
            article_event_map[link].append(event.get("name"))
            
    for article in articles:
        feed_url = article.get("feed_url")
        if feed_url in feed_title_map:
            article["feed_title"] = feed_title_map[feed_url]
        
        article_link = article.get("link")
        if article_link in article_event_map:
            article["events"] = article_event_map[article_link]
            
    return jsonify(articles)

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
    namespace = request.args.get('namespace')
    
    # Validate namespace if provided
    if namespace:
        try:
            namespace = validate_namespace_param(namespace)
        except ValueError as e:
            abort(400, description=str(e))
    
    events = fetch_from_couchdb("events")
    # Filter only actual events (legacy docs might not have 'type')
    events = [e for e in events if e.get('type', 'event') == 'event']
    
    if namespace:
        events = [e for e in events if e.get('namespace') == namespace]
        
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
    namespace = request.args.get('namespace')
    
    # Validate namespace if provided
    if namespace:
        try:
            namespace = validate_namespace_param(namespace)
        except ValueError as e:
            abort(400, description=str(e))
    
    trends = fetch_from_couchdb("trends")
    if not trends:
        trends = []
        
    if namespace:
        trends = [t for t in trends if t.get('namespace') == namespace]
        
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

@api_blueprint.route("/namespaces", methods=["GET"])
def list_namespaces():
    # Fetch all events and trends to aggregate namespaces
    events = fetch_from_couchdb("events")
    trends = fetch_from_couchdb("trends")
    
    namespaces = set()
    if events:
        for e in events:
            if e.get("namespace"):
                namespaces.add(e.get("namespace"))
    
    if trends:
        for t in trends:
            if t.get("namespace"):
                namespaces.add(t.get("namespace"))
                
    return jsonify(sorted(list(namespaces)))

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
        "iteration_interval": get_iteration_interval_setting()
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