from flask import Blueprint, jsonify, abort
import os
import requests
import urllib.parse

api_blueprint = Blueprint('api', __name__)

COUCHDB_URI = os.environ.get("COUCHDB_URI", "http://localhost:5984/")

def fetch_from_couchdb(db_name, doc_id=None):
    """Fetches data from CouchDB. If doc_id is None, lists all documents in the database."""
    # Validate that the database name is one of the allowed, trusted names
    allowed_dbs = {"feeds", "articles", "events"}
    if db_name not in allowed_dbs:
        abort(400, description="Invalid database name.")
    # Validate that the document ID contains only safe characters (alphanumeric, dash, and underscore)
    if doc_id and not __import__('re').match(r'^[A-Za-z0-9\-_]+$', doc_id):
        abort(400, description="Invalid document id.")
    try:
        if doc_id:
            safe_db_name = urllib.parse.quote(db_name, safe="")
            safe_doc_id = urllib.parse.quote(doc_id, safe="")
            response = requests.get(f"{COUCHDB_URI}{safe_db_name}/{safe_doc_id}")
        else:
            response = requests.get(f"{COUCHDB_URI}{db_name}/_all_docs", params={"include_docs": "true"})

        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        if doc_id:
            return response.json()
        else:
            # Extract documents from the _all_docs response
            docs = [row["doc"] for row in response.json()["rows"]]
            return docs
    except requests.exceptions.RequestException as e:
        print(f"Error fetching from CouchDB: {e}")
        abort(500, description=f"Error fetching from CouchDB: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        abort(500, description=f"Unexpected error: {e}")

@api_blueprint.route("/feeds", methods=["GET"])
def list_feeds():
    feeds = fetch_from_couchdb("feeds")
    # Extract only the URL from each feed document to return as a list
    feed_urls = [feed['url'] for feed in feeds]
    return jsonify(feed_urls)

@api_blueprint.route("/feeds/<feed_id>", methods=["GET"])
def get_feed(feed_id):
    feed = fetch_from_couchdb("feeds", feed_id)
    if not feed:
        abort(404, description="Feed not found")
    return jsonify(feed)

@api_blueprint.route("/articles", methods=["GET"])
def list_articles():
    articles = fetch_from_couchdb("articles")
    return jsonify(articles)

@api_blueprint.route("/articles/<article_id>", methods=["GET"])
def get_article(article_id):
    article = fetch_from_couchdb("articles", article_id)
    if not article:
        abort(404, description="Article not found")
    return jsonify(article)

@api_blueprint.route("/events", methods=["GET"])
def list_events():
    events = fetch_from_couchdb("events")
    return jsonify(events)

@api_blueprint.route("/events/<event_id>", methods=["GET"])
def get_event(event_id):
    event = fetch_from_couchdb("events", event_id)
    if not event:
        abort(404, description="Event not found")
    return jsonify(event)

def fetch_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return {"url": url, "status": "success"}
        else:
            return {"url": url, "status": "failed", "code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"url": url, "status": "error", "message": str(e)}