import os
import requests
import feedparser
import hashlib
import json
import re
import uuid
from datetime import datetime
from mcp.server.fastmcp import FastMCP, Context
from starlette_prometheus import PrometheusMiddleware, metrics
from tasks.favicon_fetcher import fetch_favicon_url

# Initialize FastMCP Server
mcp = FastMCP("Moirai MCP Server", dependencies=["requests", "feedparser"])

# Get the ASGI app and add middleware
app = mcp.sse_app()  # Call the method to get the app
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", metrics)

# Add health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Database Configuration
COUCHDB_URI = os.environ.get("COUCHDB_URI", "http://localhost:5984/").rstrip("/")
user = os.environ.get("COUCHDB_USER")
password = os.environ.get("COUCHDB_PASSWORD")
if user and password and "@" not in COUCHDB_URI:
    from urllib.parse import quote
    if "://" in COUCHDB_URI:
        scheme, host = COUCHDB_URI.split("://", 1)
    else:
        scheme, host = "http", COUCHDB_URI
    COUCHDB_URI = f"{scheme}://{quote(user)}:{quote(password)}@{host}"

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

def update_doc(db_name, doc_id, updates):
    """
    Updates a document by fetching it, applying updates, and saving it back.
    Handles revision matching.
    """
    doc = get_doc(db_name, doc_id)
    if not doc:
        return None, "Document not found."
    
    doc.update(updates)
    res = db_request("PUT", db_name, path=f"/{doc_id}", json_data=doc)
    if res.status_code in (200, 201):
        return doc_id, None
    else:
        return None, f"Failed to update doc: {res.text}"

def delete_doc(db_name, doc_id):
    """
    Deletes a document. Requires fetching first to get the revision.
    """
    doc = get_doc(db_name, doc_id)
    if not doc:
        return False, "Document not found."
    
    res = db_request("DELETE", db_name, path=f"/{doc_id}", params={"rev": doc["_rev"]})
    if res.status_code in (200, 202):
        return True, None
    else:
        return False, f"Failed to delete doc: {res.text}"

def validate_namespace(namespace: str):
    """Simple validation for namespace."""
    if not namespace or not isinstance(namespace, str):
        raise ValueError("Namespace GUID is required for this operation.")
    return True

# --- Feeds Tools (Shared) ---

@mcp.tool()
def add_feed(url: str, category: str = "general") -> str:
    """Add a new RSS feed to the shared global list."""
    # Fetch favicon for the feed
    favicon_url = fetch_favicon_url(url)
    
    feed_doc = {
        "url": url,
        "category": category,
        "added_at": datetime.now().isoformat(),
        "favicon_url": favicon_url
    }
    # Use URL hash as ID
    doc_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
    feed_doc["_id"] = doc_hash
    
    # Check if exists first to avoid 409 log
    if get_doc("feeds", doc_hash):
        return f"Feed already exists: {url}"

    res = db_request("PUT", "feeds", path=f"/{doc_hash}", json_data=feed_doc)
    if res.status_code in (200, 201):
        return f"Feed added: {url} (ID: {doc_hash})"
    else:
        return f"Error adding feed: {res.status_code} {res.text}"

@mcp.tool()
def delete_feed(url: str) -> str:
    """Delete a feed by its URL."""
    doc_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
    success, msg = delete_doc("feeds", doc_hash)
    if success:
        return f"Feed deleted: {url}"
    else:
        return f"Error deleting feed: {msg}"

@mcp.tool()
def update_feed_category(url: str, new_category: str) -> str:
    """Update the category of an existing feed."""
    doc_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
    success, msg = update_doc("feeds", doc_hash, {"category": new_category})
    if success:
        return f"Feed category updated to '{new_category}' for: {url}"
    else:
        return f"Error updating feed: {msg}"

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
        output_prefix = ""
        
        if d.bozo:
             # If parsing failed but we still got entries, just warn.
             if not d.entries:
                return f"Error parsing feed: {d.bozo_exception}"
             else:
                output_prefix = f"Warning: Feed parsing had issues ({d.bozo_exception}), but some content was recovered.\n\n"
        
        articles = []
        for entry in d.entries[:limit]:
            title = entry.get("title", "No Title")
            link = entry.get("link", "#")
            summary = entry.get("summary", "")
            summary = re.sub('<[^<]+?>', '', summary)
            articles.append(f"Title: {title}\nLink: {link}\nSummary: {summary[:200]}...\n")
            
        return output_prefix + "\n---\n".join(articles)
    except Exception as e:
        return f"Error reading feed: {e}"

@mcp.tool()
def refresh_all_feeds() -> str:
    """
    Triggers the system to fetch the latest articles from all registered feeds.
    This runs in the background. New articles will appear in the system shortly.
    """
    # The API service is named 'moirai' in docker-compose, port 8088
    # We use Basic Auth as configured in env vars or defaults
    
    # We need credentials. mcp_server doesn't strictly need them to read DB, but to call API it might.
    # Actually, the API requires auth.
    # Let's try to get credentials from env or use defaults.
    # mcp_server.py doesn't have API_USERNAME/PASSWORD env vars set in docker-compose.
    # I should add them to docker-compose for mcp-server.
    
    # For now, I'll try default "username:password" or assume the user configured it.
    # But to be robust, I should update docker-compose.
    
    api_url = "http://moirai:8088/api/feeds/refresh"
    # Fallback to localhost if running outside docker for testing?
    # But this is inside the container usually.
    
    # For now, let's just try without auth if public read is on? No, refresh is a POST, likely protected.
    # Wait, api/routes.py protects everything except specific GETs.
    
    try:
        # We need to get the creds or inject them.
        # Let's assume standard default or what's in the code for now.
        # I will update docker-compose in a moment to ensure they are passed.
        username = os.environ.get("API_USERNAME")
        password = os.environ.get("API_PASSWORD")
        
        res = requests.post(api_url, auth=(username, password), timeout=5)
        if res.status_code == 200:
            data = res.json()
            return f"Refresh triggered. Started fetching {data.get('count')} feeds."
        else:
            return f"Failed to trigger refresh. API returned {res.status_code}: {res.text}"
    except Exception as e:
        # Fallback for local testing if 'moirai' host isn't found
        if "Name or service not known" in str(e) or "Connection refused" in str(e):
             try:
                 res = requests.post("http://localhost:8088/api/feeds/refresh", auth=(username, password), timeout=5)
                 if res.status_code == 200:
                    data = res.json()
                    return f"Refresh triggered (Local). Started fetching {data.get('count')} feeds."
             except:
                 pass
        return f"Error calling refresh API: {e}"

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

@mcp.tool()
def update_event(event_id: str, namespace: str, name: str = None, description: str = None, article_links: list[str] = None) -> str:
    """Update an existing event. Only provided fields are updated. (Namespace GUID Required)"""
    validate_namespace(namespace)
    
    # Verify ownership
    existing = get_doc("events", event_id)
    if not existing or existing.get("namespace") != namespace:
        return f"Event not found in namespace {namespace}."

    updates = {}
    if name: updates["name"] = name
    if description: updates["description"] = description
    if article_links is not None: updates["article_links"] = article_links
    
    success, msg = update_doc("events", event_id, updates)
    if success:
        return f"Event {event_id} updated successfully."
    else:
        return f"Error updating event: {msg}"

@mcp.tool()
def delete_event(event_id: str, namespace: str) -> str:
    """Delete an event. (Namespace GUID Required)"""
    validate_namespace(namespace)
    
    # Verify ownership
    existing = get_doc("events", event_id)
    if not existing or existing.get("namespace") != namespace:
        return f"Event not found in namespace {namespace}."
    
    success, msg = delete_doc("events", event_id)
    if success:
        return f"Event {event_id} deleted successfully."
    else:
        return f"Error deleting event: {msg}"

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

@mcp.tool()
def update_trend(trend_id: str, namespace: str, name: str = None, description: str = None, event_ids: list[str] = None) -> str:
    """Update an existing trend. Only provided fields are updated. (Namespace GUID Required)"""
    validate_namespace(namespace)
    
    # Verify ownership
    existing = get_doc("trends", trend_id)
    if not existing or existing.get("namespace") != namespace:
        return f"Trend not found in namespace {namespace}."

    updates = {}
    if name: updates["name"] = name
    if description: updates["description"] = description
    if event_ids is not None: updates["event_ids"] = event_ids
    
    success, msg = update_doc("trends", trend_id, updates)
    if success:
        return f"Trend {trend_id} updated successfully."
    else:
        return f"Error updating trend: {msg}"

@mcp.tool()
def delete_trend(trend_id: str, namespace: str) -> str:
    """Delete a trend. (Namespace GUID Required)"""
    validate_namespace(namespace)
    
    # Verify ownership
    existing = get_doc("trends", trend_id)
    if not existing or existing.get("namespace") != namespace:
        return f"Trend not found in namespace {namespace}."
    
    success, msg = delete_doc("trends", trend_id)
    if success:
        return f"Trend {trend_id} deleted successfully."
    else:
        return f"Error deleting trend: {msg}"

@mcp.tool()
def list_namespaces() -> str:
    """List all unique namespaces found in Events and Trends."""
    # Query events and trends DBs
    events_res = db_request("GET", "events", path="/_all_docs", params={"include_docs": "true"})
    trends_res = db_request("GET", "trends", path="/_all_docs", params={"include_docs": "true"})
    
    namespaces = set()
    
    if events_res.status_code == 200:
        for row in events_res.json().get("rows", []):
            ns = row["doc"].get("namespace")
            if ns: namespaces.add(ns)
            
    if trends_res.status_code == 200:
        for row in trends_res.json().get("rows", []):
            ns = row["doc"].get("namespace")
            if ns: namespaces.add(ns)
            
    return "\n".join(sorted(list(namespaces))) if namespaces else "No namespaces found."

# Expose the SSE ASGI app for Uvicorn (already defined at top with middleware)
# app = mcp.sse_app is already set above

if __name__ == "__main__":
    # Run the server using SSE transport on port 8090
    import uvicorn
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=8090, reload=False)
