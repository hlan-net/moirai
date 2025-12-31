from flask import Blueprint, jsonify, abort, request, Response
import os
import requests
import urllib.parse
import sys
import re
from functools import wraps

api_blueprint = Blueprint('api', __name__)

COUCHDB_URI = os.environ.get("COUCHDB_URI", "http://localhost:5984/")
API_USERNAME = os.environ.get("API_USERNAME", "username")
API_PASSWORD = os.environ.get("API_PASSWORD", "password")

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

# Apply auth to all routes in this blueprint
@api_blueprint.before_request
def before_request_auth():
    if request.method == "OPTIONS":
        return # Allow CORS preflight if needed
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

def fetch_from_couchdb(db_name, doc_id=None):
    """Fetches data from CouchDB. If doc_id is None, lists all documents in the database."""
    allowed_dbs = {"feeds", "articles", "events", "trends"}
    if db_name not in allowed_dbs:
        abort(400, description="Invalid database name.")
    
    try:
        if doc_id:
            safe_db_name = urllib.parse.quote(db_name, safe="")
            safe_doc_id = urllib.parse.quote(doc_id, safe="")
            response = requests.get(f"{COUCHDB_URI}{safe_db_name}/{safe_doc_id}")
        else:
            # Check if DB exists first (lazy check for 'trends')
            requests.put(f"{COUCHDB_URI}{db_name}") 
            response = requests.get(f"{COUCHDB_URI}{db_name}/_all_docs", params={"include_docs": "true"})

        if response.status_code == 404:
             return None if doc_id else []
        
        response.raise_for_status()
        
        if doc_id:
            return response.json()
        else:
            docs = [row["doc"] for row in response.json().get("rows", [])]
            return docs
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from CouchDB: {e}")
        return None

def delete_from_couchdb(db_name, doc_id, rev):
    safe_db_name = urllib.parse.quote(db_name, safe="")
    safe_doc_id = urllib.parse.quote(doc_id, safe="")
    try:
        response = requests.delete(f"{COUCHDB_URI}{safe_db_name}/{safe_doc_id}", params={"rev": rev})
        return response.status_code in (200, 202)
    except requests.exceptions.RequestException:
        return False

def update_couchdb_doc(db_name, doc_id, doc):
    safe_db_name = urllib.parse.quote(db_name, safe="")
    safe_doc_id = urllib.parse.quote(doc_id, safe="")
    try:
        response = requests.put(f"{COUCHDB_URI}{safe_db_name}/{safe_doc_id}", json=doc)
        return response.status_code in (200, 201)
    except requests.exceptions.RequestException:
        return False

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

# --- Articles ---
@api_blueprint.route("/articles", methods=["GET"])
def list_articles():
    articles = fetch_from_couchdb("articles")
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