from datetime import datetime, timezone
import uuid  # Import uuid
from pydantic import ValidationError
from api.validation import FeedCreateRequest
from api.db import update_couchdb_doc, query_couchdb


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

        # Check if feed with this original_url already exists
        existing_feed = query_couchdb(
            "feeds", selector={"original_url": feed_url}, limit=1
        )
        if existing_feed:
            return {"status": "skipped", "reason": "exists"}

        # Generate a GUID for the feed_id
        feed_id = str(uuid.uuid4())

        # Create feed doc
        # Security: Skip favicon fetching during bulk import to prevent DoS
        feed_doc = {
            "_id": feed_id,
            "url": feed_url,  # Current URL
            "original_url": feed_url,  # Original URL
            "title": "",  # Will be filled by first fetch
            "category": "imported",
            "added_at": datetime.now(timezone.utc).isoformat(),
            "favicon_url": None,  # Will be fetched on first feed refresh
        }

        if update_couchdb_doc("feeds", feed_id, feed_doc):
            return {"status": "success"}
        else:
            return {"status": "failed", "error": "Failed to store in database"}

    except ValidationError as e:
        return {"status": "failed", "error": f"Invalid URL: {str(e)}"}
    except ValueError as e:
        return {"status": "failed", "error": f"Invalid URL: {str(e)}"}
