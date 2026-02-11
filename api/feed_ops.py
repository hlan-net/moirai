from datetime import datetime, timezone
import hashlib
from pydantic import ValidationError
from api.validation import FeedCreateRequest
from api.db import fetch_from_couchdb, update_couchdb_doc

def process_bulk_import_url(url_str):
    """
    Process a single URL for bulk import.
    Returns a dictionary with status ("success", "skipped", "failed") and error message if failed.
    """
    url_str = url_str.strip()
    if not url_str:
        return {"status": "skipped", "reason": "empty"}
    
    try:
        # Validate URL using FeedCreateRequest
        validated = FeedCreateRequest(url=url_str)
        feed_url = str(validated.url)
        
        # Generate ID
        feed_id = hashlib.sha256(feed_url.encode('utf-8')).hexdigest()
        
        # Check if feed already exists
        existing = fetch_from_couchdb("feeds", feed_id)
        if existing:
            return {"status": "skipped", "reason": "exists"}
        
        # Create feed doc
        # Security: Skip favicon fetching during bulk import to prevent DoS
        feed_doc = {
            "_id": feed_id,
            "url": feed_url,
            "title": "",  # Will be filled by first fetch
            "category": "imported",
            "added_at": datetime.now(timezone.utc).isoformat(),
            "favicon_url": None  # Will be fetched on first feed refresh
        }
        
        if update_couchdb_doc("feeds", feed_id, feed_doc):
            return {"status": "success"}
        else:
            return {"status": "failed", "error": "Failed to store in database"}
            
    except ValidationError as e:
        return {"status": "failed", "error": f"Invalid URL: {str(e)}"}
    except ValueError as e:
        return {"status": "failed", "error": f"Invalid URL: {str(e)}"}
