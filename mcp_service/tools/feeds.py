import hashlib
from datetime import datetime, timezone
from ..core import mcp, auth_required, validate_namespace
from ..db import db_request, store_doc, get_doc, delete_doc

@mcp.tool()
@auth_required
def add_feed(url: str, title: str, namespace: str, category: str = "general", api_key: str = None) -> str:
    """
    Register a new RSS feed into a specific namespace.
    
    Args:
        url: The RSS feed URL.
        title: Human-readable title for the feed.
        namespace: GUID of the namespace.
        category: Optional category (e.g., 'tech', 'finance').
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid: return err

    # Generate a unique ID based on URL and namespace to avoid duplicates within a namespace
    feed_id = hashlib.sha256(f"{url}:{namespace}".encode('utf-8')).hexdigest()
    
    feed_doc = {
        "_id": feed_id,
        "url": url,
        "title": title,
        "category": category,
        "namespace": namespace,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "type": "feed"
    }
    
    try:
        # Check if already exists in this namespace
        existing = get_doc("feeds", feed_id)
        if existing:
            return f"Feed already exists in namespace {namespace}."
            
        doc_id = store_doc("feeds", feed_doc)
        return f"Feed '{title}' added with ID: {doc_id} to namespace {namespace}"
    except Exception as e:
        return f"Error adding feed: {e}"

@mcp.tool()
@auth_required
def list_feeds(namespace: str, api_key: str = None) -> str:
    """
    List all RSS feeds registered in a specific namespace.
    
    Args:
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid: return err

    selector = {"namespace": namespace}
    try:
        res = db_request("POST", "feeds", path="/_find", json_data={"selector": selector})
        if res.status_code != 200:
            return f"Error fetching feeds: {res.text}"
            
        docs = res.json().get("docs", [])
        feeds = []
        for doc in docs:
            feeds.append(f"ID: {doc['_id']}\nTitle: {doc['title']}\nURL: {doc['url']}\nCategory: {doc.get('category', 'N/A')}\n")
            
        return "\n---\n".join(feeds) if feeds else f"No feeds found in namespace {namespace}."
    except Exception as e:
        return f"Error listing feeds: {e}"

@mcp.tool()
@auth_required
def delete_feed(feed_id: str, namespace: str, api_key: str = None) -> str:
    """
    Remove a feed from a namespace.
    
    Args:
        feed_id: The ID of the feed to delete.
        namespace: GUID of the namespace.
        api_key: Required for authentication.
    """
    valid, err = validate_namespace(namespace)
    if not valid: return err

    existing = get_doc("feeds", feed_id)
    if not existing or existing.get("namespace") != namespace:
        return "Feed not found or access denied."
        
    success, msg = delete_doc("feeds", feed_id)
    if success:
        return f"Feed {feed_id} deleted successfully from namespace {namespace}."
    else:
        return f"Error deleting feed: {msg}"
