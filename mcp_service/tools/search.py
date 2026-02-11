import json
import re
from datetime import datetime, timedelta, timezone
from ..core import mcp
from ..db import db_request

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
        
        if resp.status_code != 200:
             return json.dumps({"error": f"Search failed: {resp.text}"})

        docs = resp.json().get("docs", [])
        
        results = []
        for doc in docs:
            results.append({
                "_id": doc.get("_id"),
                "title": doc.get("title", "Untitled"),
                "link": doc.get("link", ""),
                "published": doc.get("published", ""),
                "feed_title": doc.get("feed_title", "Unknown"),
                "description": doc.get("description", "")[:200]
            })
            
        return json.dumps({
            "total": len(results),
            "query": query,
            "results": results
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Search execution error: {str(e)}"})

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
        
        if resp.status_code != 200:
             return json.dumps({"error": f"Fetch failed: {resp.text}"})
             
        docs = resp.json().get("docs", [])
        
        results = []
        for doc in docs:
             results.append({
                "_id": doc.get("_id"),
                "title": doc.get("title", "Untitled"),
                "link": doc.get("link", ""),
                "published": doc.get("published", ""),
                "feed_title": doc.get("feed_title", "Unknown"),
                "description": doc.get("description", "")[:200]
            })
            
        return json.dumps({
            "total": len(results),
            "hours": hours,
            "results": results
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Fetch execution error: {str(e)}"})

@mcp.tool()
def search_events(query: str, limit: int = 50) -> str:
    """
    Search events by name or description.
    
    Args:
        query: Search keywords (case-insensitive)
        limit: Maximum number of results (default: 50, max: 100)
    
    Returns:
        JSON string with matching events
    """
    if not query.strip():
        return json.dumps({"error": "Query cannot be empty"})
    
    if limit > 100:
        limit = 100
    
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
         
        if resp.status_code != 200:
             return json.dumps({"error": f"Search failed: {resp.text}"})
             
        docs = resp.json().get("docs", [])
        
        results = []
        for doc in docs:
            results.append({
                "_id": doc.get("_id"),
                "name": doc.get("name", "Untitled"),
                "description": doc.get("description", ""),
                "article_count": len(doc.get("article_links", []))
            })
            
        return json.dumps({
            "total": len(results),
            "query": query,
            "results": results
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Search execution error: {str(e)}"})

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
         
         if resp.status_code != 200:
             return json.dumps({"error": f"Search failed: {resp.text}"})

         docs = resp.json().get("docs", [])
         
         results = []
         for doc in docs:
            results.append({
                "_id": doc.get("_id"),
                "name": doc.get("name", "Untitled"),
                "description": doc.get("description", ""),
                "event_count": len(doc.get("event_ids", []))
            })
            
         return json.dumps({
            "total": len(results),
            "query": query,
            "results": results
        }, indent=2)
        
    except Exception as e:
         return json.dumps({"error": f"Search execution error: {str(e)}"})
