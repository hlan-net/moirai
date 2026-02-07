import os
import sys
import requests
import feedparser
import hashlib
import json
import re
import uuid
import logging
from datetime import datetime, timedelta, timezone
from mcp.server.fastmcp import FastMCP, Context
from tasks.favicon_fetcher import fetch_favicon_url
from version import get_version_string

# Import shared modules using proper Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api.db_config import COUCHDB_URI

# Configure logging with basic setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants for limits and defaults
DEFAULT_ARTICLE_LIMIT = 50
MAX_ARTICLE_LIMIT = 200
DEFAULT_SEARCH_LIMIT = 20
MAX_SEARCH_LIMIT = 100
DEFAULT_HOURS_LOOKBACK = 24
MAX_HOURS_LOOKBACK = 168  # 1 week
MAX_DESCRIPTION_LENGTH = 200  # Maximum characters for description preview

# HTTP Status Codes
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404

# Common error messages
MSG_NOT_FOUND = "not found."
MSG_EVENT_NOT_FOUND = "Event not found."
MSG_TREND_NOT_FOUND = "Trend not found."
MSG_NO_EVENTS_FOUND = "No events found."
MSG_NO_TRENDS_FOUND = "No trends found."
MSG_QUERY_EMPTY = "Query cannot be empty"
MSG_UNTITLED = "Untitled"
MSG_UNKNOWN_FEED = "Unknown"
MSG_DOC_NOT_FOUND = "Document not found."

# Initialize FastMCP Server
mcp = FastMCP("Moirai MCP Server", dependencies=["requests", "feedparser"])

# Get the ASGI app
app = mcp.sse_app()  # Call the method to get the app

# Add metrics endpoint (without middleware that breaks SSE)
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

async def health_check(request):
    """Health check endpoint for service monitoring."""
    return JSONResponse({"status": "ok"})

async def metrics_endpoint(request):
    """Metrics endpoint placeholder for Prometheus integration."""
    # Simple metrics endpoint without PrometheusMiddleware
    return Response("# Placeholder metrics endpoint\n", media_type="text/plain")

# Add routes directly instead of middleware
app.routes.append(Route("/health", health_check))
app.routes.append(Route("/metrics", metrics_endpoint))

# --- DB Helpers ---

def get_db_url(db_name):
    """Construct the full database URL from base URI and database name.
    
    Args:
        db_name: Name of the CouchDB database
        
    Returns:
        Complete URL string for the database
    """
    return f"{COUCHDB_URI}{db_name}"

def db_request(method, db_name, path="", json_data=None, params=None):
    """Execute an HTTP request against CouchDB.
    
    Args:
        method: HTTP method (GET, POST, PUT, HEAD, DELETE)
        db_name: Name of the CouchDB database
        path: Optional path within the database (default: "")
        json_data: Optional JSON data for request body (default: None)
        params: Optional query parameters (default: None)
        
    Returns:
        requests.Response object
        
    Raises:
        RuntimeError: On database connection errors (non-404 errors)
    """
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
        elif method == "DELETE":
            response = requests.delete(url, params=params)
        
        # Don't raise for 404s if we want to handle them gracefully in callers
        is_error_not_404 = (response.status_code >= HTTP_BAD_REQUEST and 
                           response.status_code != HTTP_NOT_FOUND)
        if is_error_not_404:
            logger.error(f"DB Error {method} {url}: {response.text}")
            
        return response
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Database connection error: {e}")

def get_doc(db_name, doc_id):
    """Retrieve a document from CouchDB by ID.
    
    Args:
        db_name: Name of the CouchDB database
        doc_id: Document identifier
        
    Returns:
        Document as dictionary if found, None otherwise
    """
    res = db_request("GET", db_name, path=f"/{doc_id}")
    if res.status_code == HTTP_OK:
        return res.json()
    return None

def store_doc(db_name, doc):
    """Store a document in CouchDB.
    
    Generates a hash-based ID if one is not provided in the document.
    
    Args:
        db_name: Name of the CouchDB database
        doc: Document dictionary to store
        
    Returns:
        Document ID if successful, or an error message string
        
    Raises:
        RuntimeError: If storage fails
    """
    if "_id" not in doc:
        # Generate hash ID if not present
        doc_hash = hashlib.sha256(json.dumps(doc, sort_keys=True).encode('utf-8')).hexdigest()
        doc["_id"] = doc_hash

    existing = get_doc(db_name, doc["_id"])
    if existing:
        return f"Document {doc['_id']} already exists."
    
    res = db_request("POST", db_name, json_data=doc)
    if res.status_code in (HTTP_OK, HTTP_CREATED):
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
        return None, MSG_DOC_NOT_FOUND
    
    doc.update(updates)
    res = db_request("PUT", db_name, path=f"/{doc_id}", json_data=doc)
    if res.status_code in (HTTP_OK, HTTP_CREATED):
        return doc_id, None
    else:
        return None, f"Failed to update doc: {res.text}"

def delete_doc(db_name, doc_id):
    """
    Deletes a document. Requires fetching first to get the revision.
    """
    doc = get_doc(db_name, doc_id)
    if not doc:
        return False, MSG_DOC_NOT_FOUND
    
    res = db_request("DELETE", db_name, path=f"/{doc_id}", params={"rev": doc["_rev"]})
    if res.status_code in (HTTP_OK, HTTP_ACCEPTED):
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
    except (RuntimeError, requests.exceptions.RequestException) as e:
        logger.error(f"Error creating event: {e}")
        return f"Error creating event: {e}"

@mcp.tool()
def list_events() -> str:
    """List all created events."""
    res = db_request("GET", "events", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != HTTP_OK:
        return "No events data found."
    
    try:
        rows = res.json().get("rows", [])
    except (ValueError, AttributeError) as e:
        logger.error(f"Error parsing events response: {e}")
        return "Error retrieving events."
    
    events = []
    for row in rows:
        doc = row["doc"]
        if doc.get("type") == "event":
            events.append(f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nArticles: {len(doc.get('article_links', []))}\n")
    
    return "\n---\n".join(events) if events else MSG_NO_EVENTS_FOUND

@mcp.tool()
def read_event(event_id: str) -> str:
    """Get details of a specific event."""
    doc = get_doc("events", event_id)
    if not doc:
        return MSG_EVENT_NOT_FOUND
    
    return json.dumps(doc, indent=2)

@mcp.tool()
def update_event(event_id: str, name: str = None, description: str = None, article_links: list[str] = None) -> str:
    """Update an existing event. Only provided fields are updated."""
    existing = get_doc("events", event_id)
    if not existing:
        return MSG_EVENT_NOT_FOUND
    
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
        return MSG_EVENT_NOT_FOUND
    
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
        if db_request("HEAD", "trends").status_code == HTTP_NOT_FOUND:
            db_request("PUT", "trends")

        doc_id = store_doc("trends", trend_doc)
        return f"Trend created with ID: {doc_id}"
    except (RuntimeError, requests.exceptions.RequestException) as e:
        logger.error(f"Error creating trend: {e}")
        return f"Error creating trend: {e}"

@mcp.tool()
def list_trends() -> str:
    """List all created trends."""
    if db_request("HEAD", "trends").status_code == HTTP_NOT_FOUND:
        return "No trends data found."

    res = db_request("GET", "trends", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != HTTP_OK:
        return "No trends data found."
    
    try:
        rows = res.json().get("rows", [])
    except (ValueError, AttributeError) as e:
        logger.error(f"Error parsing trends response: {e}")
        return "Error retrieving trends."
    
    trends = []
    for row in rows:
        doc = row["doc"]
        trends.append(f"ID: {doc['_id']}\nName: {doc['name']}\nDesc: {doc['description']}\nEvents: {len(doc.get('event_ids', []))}\n")
    
    return "\n---\n".join(trends) if trends else MSG_NO_TRENDS_FOUND

@mcp.tool()
def read_trend(trend_id: str) -> str:
    """Get details of a specific trend."""
    doc = get_doc("trends", trend_id)
    if not doc:
        return MSG_TREND_NOT_FOUND
    
    return json.dumps(doc, indent=2)

@mcp.tool()
def update_trend(trend_id: str, name: str = None, description: str = None, event_ids: list[str] = None) -> str:
    """Update an existing trend. Only provided fields are updated."""
    existing = get_doc("trends", trend_id)
    if not existing:
        return MSG_TREND_NOT_FOUND

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
        return MSG_TREND_NOT_FOUND
    
    success, msg = delete_doc("trends", trend_id)
    if success:
        return f"Trend {trend_id} deleted successfully."
    else:
        return f"Error deleting trend: {msg}"

# ===== SEARCH TOOLS =====

@mcp.tool()
def search_articles(query: str, date_from: str = "", date_to: str = "", limit: int = DEFAULT_ARTICLE_LIMIT) -> str:
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
        return json.dumps({"error": MSG_QUERY_EMPTY})
    
    if limit > MAX_ARTICLE_LIMIT:
        limit = MAX_ARTICLE_LIMIT
    
    safe_query = re.escape(query)
    
    # Build Mango selector
    selector = {
        "$or": [
            {"title": {"$regex": f"(?i){safe_query}"}},
            {"description": {"$regex": f"(?i){safe_query}"}},
            {"content": {"$regex": f"(?i){safe_query}"}}
        ]
    }
    
    # Add date range filters
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from)
            if from_dt.tzinfo is None:
                from_dt = from_dt.replace(tzinfo=timezone.utc)
            selector["published"] = {"$gte": from_dt.isoformat()}
        except ValueError:
            return json.dumps({"error": "Invalid date_from format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"})
    
    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to)
            if to_dt.tzinfo is None:
                to_dt = to_dt.replace(tzinfo=timezone.utc)
            # Combine with existing published filter if from_dt exists
            if "published" in selector:
                selector["published"]["$lte"] = to_dt.isoformat()
            else:
                selector["published"] = {"$lte": to_dt.isoformat()}
        except ValueError:
            return json.dumps({"error": "Invalid date_to format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"})
            
    # Execute query
    try:
        query_payload = {
            "selector": selector,
            "limit": limit,
            "sort": [{"published": "desc"}] if "published" in selector else None,
            # We need to exclude design docs, though Mango usually handles this.
            # Fields projection to reduce bandwidth
            "fields": ["_id", "title", "link", "published", "feed_title", "description"]
        }
        
        # Remove sort if it's None to avoid errors
        if not query_payload["sort"]:
            del query_payload["sort"]

        resp = db_request("POST", "articles", "/_find", json_data=query_payload)
        
        if resp.status_code != HTTP_OK:
             return json.dumps({"error": f"Search failed: {resp.text}"})

        try:
            docs = resp.json().get("docs", [])
        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing search response: {e}")
            return json.dumps({"error": "Error parsing search results"})
        
        results = []
        for doc in docs:
            results.append({
                "_id": doc.get("_id"),
                "title": doc.get("title", MSG_UNTITLED),
                "link": doc.get("link", ""),
                "published": doc.get("published", ""),
                "feed_title": doc.get("feed_title", MSG_UNKNOWN_FEED),
                "description": doc.get("description", "")[:MAX_DESCRIPTION_LENGTH]
            })
            
        return json.dumps({
            "total": len(results),
            "query": query,
            "results": results
        }, indent=2)

    except requests.exceptions.RequestException as e:
        logger.error(f"Search execution error: {e}")
        return json.dumps({"error": f"Search execution error: {str(e)}"})

@mcp.tool()
def get_recent_articles(hours: int = DEFAULT_HOURS_LOOKBACK, limit: int = DEFAULT_ARTICLE_LIMIT) -> str:
    """
    Get most recent articles from all feeds.
    
    Args:
        hours: Number of hours to look back (default: 24, max: 168)
        limit: Maximum number of results (default: 50, max: 200)
    
    Returns:
        JSON string with recent articles sorted by date
    """
    if hours > MAX_HOURS_LOOKBACK:
        hours = MAX_HOURS_LOOKBACK
    if limit > MAX_ARTICLE_LIMIT:
        limit = MAX_ARTICLE_LIMIT
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Mango Query
    selector = {
        "published": {"$gte": cutoff.isoformat()}
    }
    
    try:
        query_payload = {
            "selector": selector,
            "limit": limit,
            "sort": [{"published": "desc"}],
            "fields": ["_id", "title", "link", "published", "feed_title", "description"]
        }
        
        resp = db_request("POST", "articles", "/_find", json_data=query_payload)
        
        if resp.status_code != HTTP_OK:
             return json.dumps({"error": f"Fetch failed: {resp.text}"})
             
        try:
            docs = resp.json().get("docs", [])
        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing fetch response: {e}")
            return json.dumps({"error": "Error retrieving articles"})
        
        results = []
        for doc in docs:
             results.append({
                "_id": doc.get("_id"),
                "title": doc.get("title", MSG_UNTITLED),
                "link": doc.get("link", ""),
                "published": doc.get("published", ""),
                "feed_title": doc.get("feed_title", MSG_UNKNOWN_FEED),
                "description": doc.get("description", "")[:MAX_DESCRIPTION_LENGTH]
            })
            
        return json.dumps({
            "total": len(results),
            "hours": hours,
            "results": results
        }, indent=2)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Fetch execution error: {e}")
        return json.dumps({"error": f"Fetch execution error: {str(e)}"})

@mcp.tool()
def search_events(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> str:
    """
    Search events by keyword in name or description.
    
    Args:
        query: Search keywords (case-insensitive)
        limit: Maximum number of results (default: 20, max: 100)
    
    Returns:
        JSON string with matching events
    """
    if not query.strip():
        return json.dumps({"error": MSG_QUERY_EMPTY})
    
    if limit > MAX_SEARCH_LIMIT:
        limit = MAX_SEARCH_LIMIT
    
    safe_query = re.escape(query)
    
    # Mango selector
    selector = {
        "$or": [
            {"name": {"$regex": f"(?i){safe_query}"}},
            {"description": {"$regex": f"(?i){safe_query}"}}
        ]
    }
    
    try:
        query_payload = {
            "selector": selector,
            "limit": limit,
            "fields": ["_id", "name", "description", "article_links"]
        }
        
        resp = db_request("POST", "events", "/_find", json_data=query_payload)
        
        if resp.status_code != HTTP_OK:
            return json.dumps({"error": f"Search failed: {resp.text}"})
            
        try:
            docs = resp.json().get("docs", [])
        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing events search response: {e}")
            return json.dumps({"error": "Error searching events"})
        
        results = []
        for doc in docs:
            results.append({
                "_id": doc.get("_id"),
                "name": doc.get("name", MSG_UNTITLED),
                "description": doc.get("description", ""),
                "article_count": len(doc.get("article_links", []))
            })
            
        return json.dumps({
            "total": len(results),
            "query": query,
            "results": results
        }, indent=2)

    except requests.exceptions.RequestException as e:
        logger.error(f"Search execution error: {e}")
        return json.dumps({"error": f"Search execution error: {str(e)}"})

@mcp.tool()
def search_trends(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> str:
    """
    Search trends by keyword in title or description.
    
    Args:
        query: Search keywords (case-insensitive)
        limit: Maximum number of results (default: 20, max: 100)
    
    Returns:
        JSON string with matching trends
    """
    if not query.strip():
        return json.dumps({"error": MSG_QUERY_EMPTY})
    
    if limit > MAX_SEARCH_LIMIT:
        limit = MAX_SEARCH_LIMIT
    
    safe_query = re.escape(query)
    
    # Mango selector
    selector = {
        "$or": [
            {"name": {"$regex": f"(?i){safe_query}"}},
            {"description": {"$regex": f"(?i){safe_query}"}}
        ]
    }
    
    try:
        query_payload = {
            "selector": selector,
            "limit": limit,
            "fields": ["_id", "name", "description", "event_ids"]
        }
        
        resp = db_request("POST", "trends", "/_find", json_data=query_payload)
         
        if resp.status_code != HTTP_OK:
             return json.dumps({"error": f"Search failed: {resp.text}"})

        try:
            docs = resp.json().get("docs", [])
        except (ValueError, AttributeError) as e:
            logger.error(f"Error parsing trends search response: {e}")
            return json.dumps({"error": "Error searching trends"})
        
        results = []
        for doc in docs:
            results.append({
                "_id": doc.get("_id"),
                "name": doc.get("name", MSG_UNTITLED),
                "description": doc.get("description", ""),
                "event_count": len(doc.get("event_ids", []))
            })
            
        return json.dumps({
            "total": len(results),
            "query": query,
            "results": results
        }, indent=2)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Search execution error: {e}")
        return json.dumps({"error": f"Search execution error: {str(e)}"})

# Expose the SSE ASGI app for Uvicorn (already defined at top with middleware)
# app = mcp.sse_app is already set above

if __name__ == "__main__":
    # Log version info
    logger.info(f"{get_version_string()} starting...")
    
    # Run the server using SSE transport on port 8090
    import uvicorn
    uvicorn.run("mcp_server:app", host="0.0.0.0", port=8090, reload=False)

