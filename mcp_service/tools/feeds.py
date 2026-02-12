import json
import hashlib
from datetime import datetime, timezone
import requests
from ..core import mcp
from ..db import store_doc, db_request, get_doc, update_doc, delete_doc
from tasks.fetch_feed_task import FetchFeedTask

# --- Feeds Tools ---

@mcp.tool()
def add_feed(url: str, title: str = "", category: str = "general") -> str:
    """
    Register a new RSS feed source.
    
    Args:
        url: The full URL to the RSS/Atom feed
        title: Optional title for the feed
        category: Optional category (e.g., 'tech', 'news', 'linux')
    """
    feed_id = hashlib.sha256(url.encode('utf-8')).hexdigest()
    
    feed_doc = {
        "_id": feed_id,
        "url": url,
        "title": title,
        "category": category,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "type": "feed"
    }
    
    try:
        # Check if already exists
        existing = get_doc("feeds", feed_id)
        if existing:
            return f"Feed already exists: {url}"
            
        res = store_doc("feeds", feed_doc)
        return f"Feed registered successfully with ID: {res}"
    except Exception as e:
        return f"Error registering feed: {e}"

@mcp.tool()
def list_feeds() -> str:
    """List all registered RSS feeds."""
    res = db_request("GET", "feeds", path="/_all_docs", params={"include_docs": "true"})
    if res.status_code != 200:
        return "No feeds data found."
    
    rows = res.json().get("rows", [])
    feeds = []
    for row in rows:
        doc = row["doc"]
        # Skip design docs
        if doc.get("_id", "").startswith("_design/"):
            continue
        feeds.append(f"Title: {doc.get('title', 'Untitled')}\nURL: {doc.get('url')}\nCategory: {doc.get('category', 'none')}\nID: {doc['_id']}\n")
    
    return "\n---\n".join(feeds) if feeds else "No feeds found."

@mcp.tool()
def read_feed(url: str, limit: int = 20) -> str:
    """
    Fetch and process articles from a specific RSS feed URL.
    This triggers a live fetch and returns the latest articles.
    
    Args:
        url: The RSS feed URL to fetch
        limit: Max number of articles to return (default: 20)
    """
    try:
        # We use FetchFeedTask logic but synchronously for the tool response
        # or we trigger it and then fetch from articles DB?
        # Actually, to be responsive, we should probably fetch it here or use ArticleProcessor directly.
        
        from tasks.article_processor import ArticleProcessor
        import requests
        
        headers = {'User-Agent': 'MoiraiBot/1.0'}
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return f"Failed to fetch feed: HTTP {response.status_code}"
            
        processor = ArticleProcessor()
        feed_title, articles = processor.process_feed(url, response.text)
        
        # Store articles in background
        count = 0
        for article in articles:
            processor.store_article(article)
            count += 1
            
        # Return the latest few
        results = articles[:limit]
        
        output = [f"Feed: {feed_title}", f"Processed {len(articles)} articles, stored {count}."]
        for a in results:
            output.append(f"- {a['title']} ({a['link']}) [{a.get('language', 'unknown')}]")
            
        return "\n".join(output)
        
    except Exception as e:
        return f"Error reading feed: {e}"

@mcp.tool()
def update_feed_category(url: str, new_category: str) -> str:
    """Update the category of an existing feed."""
    feed_id = hashlib.sha256(url.encode('utf-8')).hexdigest()
    success, msg = update_doc("feeds", feed_id, {"category": new_category})
    if success:
        return f"Feed {url} category updated to {new_category}."
    else:
        return f"Error updating feed: {msg}"

@mcp.tool()
def delete_feed(url: str) -> str:
    """Unregister a feed source."""
    feed_id = hashlib.sha256(url.encode('utf-8')).hexdigest()
    success, msg = delete_doc("feeds", feed_id)
    if success:
        return f"Feed {url} deleted successfully."
    else:
        return f"Error deleting feed: {msg}"
