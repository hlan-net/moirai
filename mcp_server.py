import os
import requests
import feedparser
import hashlib
import json
import re
import uuid
from datetime import datetime
from mcp.server.fastmcp import FastMCP, Context

# Initialize FastMCP Server
mcp = FastMCP("Moirai MCP Server", dependencies=["requests", "feedparser"])

# Database Configuration
COUCHDB_URI = os.environ.get("COUCHDB_URI", "http://admin:password@localhost:5984/")
if not COUCHDB_URI.endswith("/"):
    COUCHDB_URI += "/"

# --- DB Helpers ---

def get_db_url(db_name):
    return f"{COUCHDB_URI}{db_name}"

def db_request(method, db_name, path="", json_data=None, params=None):
    url = f"{get_db_url(db_name)}{path}"
    try:
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            response = requests.post(url, json=json_data)
        elif method == "PUT":
            response = requests.put(url, json=json_data)
        elif method == "HEAD":
            response = requests.head(url)
        
        # Don't raise for 404s if we want to handle them gracefully in callers
        if response.status_code >= 400 and response.status_code != 404:
            print(f"DB Error {method} {url}: {response.text}")
            
        return response
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Database connection error: {e}")

def get_doc(db_name, doc_id):
    res = db_request("GET", db_name, path=f"/{doc_id}")
    if res.status_code == 200:
        return res.json()
    return None

def store_doc(db_name, doc):
    if "_id" not in doc:
        # Generate hash ID if not present
        doc_hash = hashlib.sha256(json.dumps(doc, sort_keys=True).encode('utf-8')).hexdigest()
        doc["_id"] = doc_hash

    existing = get_doc(db_name, doc["_id"])
    if existing:
        return f"Document {doc['_id']} already exists."
    
    res = db_request("POST", db_name, json_data=doc)
    if res.status_code in (200, 201):
        return doc["_id"]
    else:
        raise RuntimeError(f"Failed to store doc: {res.text}")

def validate_namespace(namespace: str):
    """Simple validation for namespace."""
    if not namespace or not isinstance(namespace, str):
        raise ValueError("Namespace GUID is required for this operation.")
    return True

# --- Feeds Tools (Shared) ---

@mcp.tool()
def add_feed(url: str, category: str = "general") -> str:
    """Add a new RSS feed to the shared global list."""
    feed_doc = {
        "url": url,
        "category": category,
        "added_at": datetime.now().isoformat()
    }
    # Use URL hash as ID
    doc_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
    feed_doc["_id"] = doc_hash
    
    res = db_request("PUT", "feeds", path=f"/{doc_hash}", json_data=feed_doc)
    if res.status_code in (200, 201):
        return f"Feed added: {url} (ID: {doc_hash})"
    elif res.status_code == 409:
        return f"Feed already exists: {url}"
    else:
        return f"Error adding feed: {res.status_code} {res.text}"

@mcp.tool()
def list_feeds() -> str:
    """List all registered RSS feeds (Global)."""
    res = db_request("GET", "feeds", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != 200:
        return "Error fetching feeds or database empty."
    
    rows = res.json().get("rows", [])
    feeds = []
    for row in rows:
        doc = row["doc"]
        feeds.append(f"- {doc.get('url')} (Category: {doc.get('category', 'unknown')})")
    
    return "\n".join(feeds) if feeds else "No feeds found."

@mcp.tool()
def read_feed(url: str, limit: int = 5) -> str:
    """
    Fetch and parse articles from a specific RSS feed URL.
    Returns a list of the latest articles.
    """
    try:
        d = feedparser.parse(url)
        if d.bozo:
             return f"Error parsing feed: {d.bozo_exception}"
        
        articles = []
        for entry in d.entries[:limit]:
            title = entry.get("title", "No Title")
            link = entry.get("link", "#")
            summary = entry.get("summary", "")
            summary = re.sub('<[^<]+?>', '', summary)
            articles.append(f"Title: {title}\nLink: {link}\nSummary: {summary[:200]}...\n")
            
        return "\n---\n".join(articles)
    except Exception as e:
        return f"Error reading feed: {e}"

# --- Events Tools (Namespaced) ---

@mcp.tool()
def add_event(name: str, description: str, article_links: list[str], namespace: str = None) -> str:
    """
    Create a new Event grouping multiple articles.
    If namespace is not provided, a new GUID will be generated.
    If namespace is provided, it will be used (effectively creating it if new).
    """
    if not namespace:
        namespace = str(uuid.uuid4())
        msg_prefix = f"New namespace generated: {namespace}\n"
    else:
        msg_prefix = f"Using namespace: {namespace}\n"

    event_doc = {
        "name": name,
        "description": description,
        "article_links": article_links,
        "namespace": namespace,
        "created_at": datetime.now().isoformat(),
        "type": "event"
    }
    
    try:
        doc_id = store_doc("events", event_doc)
        return f"{msg_prefix}Event created with ID: {doc_id}"
    except Exception as e:
        return f"Error creating event: {e}"

@mcp.tool()
def list_events(namespace: str) -> str:
    """List all created events for a specific namespace GUID (Required)."""
    validate_namespace(namespace)
    
    res = db_request("GET", "events", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != 200:
        return "No events data found."
    
    rows = res.json().get("rows", [])
    events = []
    for row in rows:
        doc = row["doc"]
        if doc.get("type") == "event" and doc.get("namespace") == namespace:
            events.append(f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nArticles: {len(doc.get('article_links', []))}\n")
    
    return "\n---\n".join(events) if events else f"No data found for namespace {namespace}."

@mcp.tool()
def read_event(event_id: str, namespace: str) -> str:
    """Get details of a specific event (Namespace GUID Required)."""
    validate_namespace(namespace)
    
    doc = get_doc("events", event_id)
    if not doc or doc.get("namespace") != namespace:
        return f"No data found for this event in namespace {namespace}."
    
    return json.dumps(doc, indent=2)

# --- Trends Tools (Namespaced) ---

@mcp.tool()
def add_trend(name: str, description: str, event_ids: list[str], namespace: str = None) -> str:
    """
    Create a new Trend grouping multiple events.
    If namespace is not provided, a new GUID will be generated.
    """
    if not namespace:
        namespace = str(uuid.uuid4())
        msg_prefix = f"New namespace generated: {namespace}\n"
    else:
        msg_prefix = f"Using namespace: {namespace}\n"

    trend_doc = {
        "name": name,
        "description": description,
        "event_ids": event_ids,
        "namespace": namespace,
        "created_at": datetime.now().isoformat(),
        "type": "trend"
    }
    
    try:
        if db_request("HEAD", "trends").status_code == 404:
            db_request("PUT", "trends")

        doc_id = store_doc("trends", trend_doc)
        return f"{msg_prefix}Trend created with ID: {doc_id}"
    except Exception as e:
        return f"Error creating trend: {e}"

@mcp.tool()
def list_trends(namespace: str) -> str:
    """List all created trends for a specific namespace GUID (Required)."""
    validate_namespace(namespace)
    
    if db_request("HEAD", "trends").status_code == 404:
        return "No trends data found."

    res = db_request("GET", "trends", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != 200:
        return "No trends data found."
    
    rows = res.json().get("rows", [])
    trends = []
    for row in rows:
        doc = row["doc"]
        if doc.get("namespace") == namespace:
            trends.append(f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nEvents: {len(doc.get('event_ids', []))}\n")
    
    return "\n---\n".join(trends) if trends else f"No data found for namespace {namespace}."

@mcp.tool()
def read_trend(trend_id: str, namespace: str) -> str:
    """Get details of a specific trend (Namespace GUID Required)."""
    validate_namespace(namespace)
    
    doc = get_doc("trends", trend_id)
    if not doc or doc.get("namespace") != namespace:
        return f"No data found for this trend in namespace {namespace}."
    
    
    return json.dumps(doc, indent=2)

# Expose the SSE ASGI app for Uvicorn
app = mcp.sse_app

if __name__ == "__main__":
    # Run the server using SSE transport on port 8090
    mcp.run(transport="sse")
