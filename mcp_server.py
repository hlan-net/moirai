import os
import requests
import feedparser
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP, Context
from tasks.favicon_fetcher import fetch_favicon_url
from version import get_version_string

# Initialize FastMCP Server
mcp = FastMCP("Moirai MCP Server", dependencies=["requests", "feedparser"])

# Get the ASGI app
app = mcp.sse_app()  # Call the method to get the app

# Add metrics endpoint (without middleware that breaks SSE)
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

async def health_check(request):
    return JSONResponse({"status": "ok"})

async def metrics_endpoint(request):
    # Simple metrics endpoint without PrometheusMiddleware
    return Response("# Placeholder metrics endpoint\n", media_type="text/plain")

# Add routes directly instead of middleware
app.routes.append(Route("/health", health_check))
app.routes.append(Route("/metrics", metrics_endpoint))

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

# --- Events Tools ---

@mcp.tool()
def add_event(name: str, description: str, article_links: list[str]) -> str:
    """
    Create a new Event grouping multiple related articles about a SINGLE occurrence.
    
    An Event represents one significant story covered by multiple sources.
    Use this when different articles report on the same announcement, incident, or development.
    """
    event_doc = {
        "name": name,
        "description": description,
        "article_links": article_links,
        "created_at": datetime.now().isoformat(),
        "type": "event"
    }
    
    try:
        doc_id = store_doc("events", event_doc)
        return f"Event created with ID: {doc_id}"
    except Exception as e:
        return f"Error creating event: {e}"

@mcp.tool()
def list_events() -> str:
    """List all created events."""
    res = db_request("GET", "events", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != 200:
        return "No events data found."
    
    rows = res.json().get("rows", [])
    events = []
    for row in rows:
        doc = row["doc"]
        if doc.get("type") == "event":
            events.append(f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nArticles: {len(doc.get('article_links', []))}\n")
    
    return "\n---\n".join(events) if events else "No events found."

@mcp.tool()
def read_event(event_id: str) -> str:
    """Get details of a specific event."""
    doc = get_doc("events", event_id)
    if not doc:
        return "Event not found."
    
    return json.dumps(doc, indent=2)

@mcp.tool()
def update_event(event_id: str, name: str = None, description: str = None, article_links: list[str] = None) -> str:
    """Update an existing event. Only provided fields are updated."""
    existing = get_doc("events", event_id)
    if not existing:
        return "Event not found."
    
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
def delete_event(event_id: str) -> str:
    """Delete an event."""
    existing = get_doc("events", event_id)
    if not existing:
        return "Event not found."
    
    success, msg = delete_doc("events", event_id)
    if success:
        return f"Event {event_id} deleted successfully."
    else:
        return f"Error deleting event: {msg}"

# --- Trends Tools ---

@mcp.tool()
def add_trend(name: str, description: str, event_ids: list[str]) -> str:
    """
    Create a new Trend grouping multiple related events into a pattern.
    
    A Trend represents a broader theme or pattern emerging from multiple distinct events over time.
    """
    trend_doc = {
        "name": name,
        "description": description,
        "event_ids": event_ids,
        "created_at": datetime.now().isoformat(),
        "type": "trend"
    }
    
    try:
        if db_request("HEAD", "trends").status_code == 404:
            db_request("PUT", "trends")

        doc_id = store_doc("trends", trend_doc)
        return f"Trend created with ID: {doc_id}"
    except Exception as e:
        return f"Error creating trend: {e}"

@mcp.tool()
def list_trends() -> str:
    """List all created trends."""
    if db_request("HEAD", "trends").status_code == 404:
        return "No trends data found."

    res = db_request("GET", "trends", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != 200:
        return "No trends data found."
    
    rows = res.json().get("rows", [])
    trends = []
    for row in rows:
        doc = row["doc"]
        trends.append(f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nEvents: {len(doc.get('event_ids', []))}\n")
    
    return "\n---\n".join(trends) if trends else "No trends found."

@mcp.tool()
def read_trend(trend_id: str) -> str:
    """Get details of a specific trend."""
    doc = get_doc("trends", trend_id)
    if not doc:
        return "Trend not found."
    
    return json.dumps(doc, indent=2)

@mcp.tool()
def update_trend(trend_id: str, name: str = None, description: str = None, event_ids: list[str] = None) -> str:
    """Update an existing trend. Only provided fields are updated."""
    existing = get_doc("trends", trend_id)
    if not existing:
        return "Trend not found."

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
def delete_trend(trend_id: str) -> str:
    """Delete a trend."""
    existing = get_doc("trends", trend_id)
    if not existing:
        return "Trend not found."
    
    success, msg = delete_doc("trends", trend_id)
    if success:
        return f"Trend {trend_id} deleted successfully."
    else:
        return f"Error deleting trend: {msg}"

# ===== SEARCH TOOLS =====

@mcp.tool()
def search_articles(query: str, date_from: str = "", date_to: str = "", limit: int = 50) -> str:
    """
    Search articles by keyword across title, description, and content.
    
    Args:
        query: Search keywords (case-insensitive)
        date_from: Optional start date (ISO format: 2026-02-05)
        date_to: Optional end date (ISO format: 2026-02-05)
        limit: Maximum number of results (default: 50, max: 200)
    
    Returns:
        JSON string with matching articles
    """
    if not query.strip():
        return json.dumps({"error": "Query cannot be empty"})
    
    if limit > 200:
        limit = 200
    
    # Get all articles
    resp = db_request("GET", "articles", "/_all_docs", params={"include_docs": True})
    if resp.status_code != 200:
        return json.dumps({"error": "Failed to fetch articles"})
    
    all_docs = resp.json().get("rows", [])
    query_lower = query.lower()
    results = []
    
    # Parse dates if provided
    from_dt = None
    to_dt = None
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from)
        except ValueError:
            pass
    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to)
        except ValueError:
            pass
    
    for row in all_docs:
        doc = row.get("doc", {})
        if doc.get("_id", "").startswith("_design"):
            continue
        
        # Check date range
        if from_dt or to_dt:
            pub_str = doc.get("published", "")
            if pub_str:
                try:
                    pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                    if from_dt and pub_dt < from_dt:
                        continue
                    if to_dt and pub_dt > to_dt:
                        continue
                except (ValueError, AttributeError):
                    pass
        
        # Search in title, description, content
        title = doc.get("title", "").lower()
        description = doc.get("description", "").lower()
        content = doc.get("content", "").lower()
        
        if query_lower in title or query_lower in description or query_lower in content:
            results.append({
                "_id": doc.get("_id"),
                "title": doc.get("title", "Untitled"),
                "link": doc.get("link", ""),
                "published": doc.get("published", ""),
                "feed_title": doc.get("feed_title", "Unknown"),
                "description": doc.get("description", "")[:200]  # Truncate
            })
        
        if len(results) >= limit:
            break
    
    return json.dumps({
        "total": len(results),
        "query": query,
        "results": results
    }, indent=2)

@mcp.tool()
def get_recent_articles(hours: int = 24, limit: int = 50) -> str:
    """
    Get most recent articles from all feeds.
    
    Args:
        hours: Number of hours to look back (default: 24, max: 168)
        limit: Maximum number of results (default: 50, max: 200)
    
    Returns:
        JSON string with recent articles sorted by date
    """
    if hours > 168:  # Max 1 week
        hours = 168
    if limit > 200:
        limit = 200
    
    # Get all articles
    resp = db_request("GET", "articles", "/_all_docs", params={"include_docs": True})
    if resp.status_code != 200:
        return json.dumps({"error": "Failed to fetch articles"})
    
    all_docs = resp.json().get("rows", [])
    cutoff = datetime.now() - timedelta(hours=hours)
    results = []
    
    for row in all_docs:
        doc = row.get("doc", {})
        if doc.get("_id", "").startswith("_design"):
            continue
        
        pub_str = doc.get("published", "")
        if pub_str:
            try:
                pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                if pub_dt >= cutoff:
                    results.append({
                        "_id": doc.get("_id"),
                        "title": doc.get("title", "Untitled"),
                        "link": doc.get("link", ""),
                        "published": pub_str,
                        "feed_title": doc.get("feed_title", "Unknown"),
                        "description": doc.get("description", "")[:200],
                        "_sort_date": pub_dt
                    })
            except (ValueError, AttributeError):
                pass
    
    # Sort by date descending
    results.sort(key=lambda x: x.get("_sort_date", datetime.min), reverse=True)
    
    # Remove sort key and limit
    for r in results:
        r.pop("_sort_date", None)
    
    return json.dumps({
        "total": len(results[:limit]),
        "hours": hours,
        "results": results[:limit]
    }, indent=2)

@mcp.tool()
def search_events(query: str, limit: int = 20) -> str:
    """
    Search events by keyword in title or description.
    
    Args:
        query: Search keywords (case-insensitive)
        limit: Maximum number of results (default: 20, max: 100)
    
    Returns:
        JSON string with matching events
    """
    if not query.strip():
        return json.dumps({"error": "Query cannot be empty"})
    
    if limit > 100:
        limit = 100
    
    resp = db_request("GET", "events", "/_all_docs", params={"include_docs": True})
    if resp.status_code != 200:
        return json.dumps({"error": "Failed to fetch events"})
    
    all_docs = resp.json().get("rows", [])
    query_lower = query.lower()
    results = []
    
    for row in all_docs:
        doc = row.get("doc", {})
        if doc.get("_id", "").startswith("_design"):
            continue
        
        name = doc.get("name", "").lower()
        description = doc.get("description", "").lower()
        
        if query_lower in name or query_lower in description:
            results.append({
                "_id": doc.get("_id"),
                "name": doc.get("name", "Untitled"),
                "description": doc.get("description", ""),
                "article_count": len(doc.get("article_links", []))
            })
        
        if len(results) >= limit:
            break
    
    return json.dumps({
        "total": len(results),
        "query": query,
        "results": results
    }, indent=2)

@mcp.tool()
def search_trends(query: str, limit: int = 20) -> str:
    """
    Search trends by keyword in title or description.
    
    Args:
        query: Search keywords (case-insensitive)
        limit: Maximum number of results (default: 20, max: 100)
    
    Returns:
        JSON string with matching trends
    """
    if not query.strip():
        return json.dumps({"error": "Query cannot be empty"})
    
    if limit > 100:
        limit = 100
    
    resp = db_request("GET", "trends", "/_all_docs", params={"include_docs": True})
    if resp.status_code != 200:
        return json.dumps({"error": "Failed to fetch trends"})
    
    all_docs = resp.json().get("rows", [])
    query_lower = query.lower()
    results = []
    
    for row in all_docs:
        doc = row.get("doc", {})
        if doc.get("_id", "").startswith("_design"):
            continue
        
        title = doc.get("title", "").lower()
        description = doc.get("description", "").lower()
        
        if query_lower in title or query_lower in description:
            results.append({
                "_id": doc.get("_id"),
                "title": doc.get("title", "Untitled"),
                "description": doc.get("description", ""),
                "event_count": len(doc.get("event_ids", []))
            })
        
        if len(results) >= limit:
            break
    
    return json.dumps({
        "total": len(results),
        "query": query,
        "results": results
    }, indent=2)

# Expose the SSE ASGI app for Uvicorn (already defined at top with middleware)
# app = mcp.sse_app is already set above

if __name__ == "__main__":
    # Print version info
    print(f"{get_version_string()} starting...", flush=True)
    
    # Run the server using SSE transport on port 8090
    import uvicorn
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=8090, reload=False)

