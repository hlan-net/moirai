import hashlib
import requests
from datetime import datetime, timezone
from ..core import mcp, auth_required, validate_userspace
from ..db import db_request, store_doc, get_doc, delete_doc, update_doc
from .constants import ERROR_FEED_NOT_FOUND_OR_DENIED
from .userspace import build_userspace_selector, extract_userspace, with_userspace
from ..responses import (
    success,
    error,
    validation_error,
    not_found_error,
    transient_error,
    internal_error,
    MCPErrorCode,
    NextAction,
)

@mcp.tool()
@auth_required
def add_feed(
    url: str, title: str, userspace: str, category: str = "general"
) -> dict:
    """
    Register a new RSS feed into a specific userspace.

    Args:
        url: The RSS feed URL.
        title: Human-readable title for the feed.
        userspace: GUID of the userspace.
        category: Optional category (e.g., 'tech', 'finance').
        
    Returns:
        Standardized MCPResponse as dict with:
        - status: success/error
        - data: {feed_id, url, title, category} on success
        - error_code: canonical code on error
        - retryable: bool indicating if operation can be retried
        - next_action: suggested next step for agent
    """
    # Validate userspace
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    # Generate a unique ID based on URL and userspace to avoid duplicates within a userspace
    feed_id = hashlib.sha256(f"{url}:{userspace}".encode("utf-8")).hexdigest()

    feed_doc = {
        "_id": feed_id,
        "url": url,
        "original_url": url,
        "title": title,
        "category": category,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "type": "feed",
    }
    with_userspace(feed_doc, userspace)

    try:
        # Check if already exists in this userspace
        existing = get_doc("feeds", feed_id)
        if existing:
            return error(
                error_code=MCPErrorCode.DUPLICATE_RESOURCE,
                message=f"Feed '{title}' already exists in userspace {userspace}",
                retryable=False,
                next_action=NextAction.NONE,  # Not an error - feed already registered
            ).to_dict()

        doc_id = store_doc("feeds", feed_doc)
        return success(
            data={
                "feed_id": doc_id,
                "url": url,
                "title": title,
                "category": category,
                "userspace": userspace,
            },
            message=f"Feed '{title}' added successfully to userspace {userspace}",
        ).to_dict()
        
    except requests.exceptions.Timeout:
        return transient_error(
            message="Database operation timed out while adding feed",
            retry_after_ms=2000,
            max_retries=3,
        ).to_dict()
        
    except requests.exceptions.ConnectionError:
        return transient_error(
            message="Failed to connect to database while adding feed",
            retry_after_ms=5000,
            max_retries=3,
        ).to_dict()
        
    except Exception as e:
        return internal_error(
            message=f"Unexpected error adding feed: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def list_feeds(userspace: str) -> dict:
    """
    List all RSS feeds registered in a specific userspace.

    Args:
        userspace: GUID of the userspace.
        
    Returns:
        Standardized MCPResponse as dict with:
        - status: success/error
        - data: {feeds: [{id, title, url, category, added_at}], count: int}
        - error_code: canonical code on error
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    selector = build_userspace_selector(userspace)
    try:
        res = db_request(
            "POST", "feeds", path="/_find", json_data={"selector": selector}
        )
        
        if res.status_code == 404:
            return not_found_error("database", "feeds", None).to_dict()
        
        if res.status_code >= 500:
            return transient_error(
                message=f"Database error fetching feeds: HTTP {res.status_code}",
                retry_after_ms=2000,
            ).to_dict()
        
        if res.status_code != 200:
            return internal_error(
                message=f"Unexpected error fetching feeds: {res.text}"
            ).to_dict()

        docs = res.json().get("docs", [])
        feeds = []
        for doc in docs:
            feeds.append({
                "id": doc["_id"],
                "title": doc.get("title", "Untitled"),
                "url": doc.get("url", ""),
                "category": doc.get("category", "general"),
                "added_at": doc.get("added_at"),
            })

        return success(
            data={
                "feeds": feeds,
                "count": len(feeds),
                "userspace": userspace,
            },
            message=f"Found {len(feeds)} feed(s) in userspace {userspace}",
        ).to_dict()
        
    except requests.exceptions.Timeout:
        return transient_error(
            message="Database operation timed out while listing feeds",
            retry_after_ms=2000,
        ).to_dict()
        
    except requests.exceptions.ConnectionError:
        return transient_error(
            message="Failed to connect to database while listing feeds",
            retry_after_ms=5000,
        ).to_dict()
        
    except Exception as e:
        return internal_error(
            message=f"Unexpected error listing feeds: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def delete_feed(feed_id: str, userspace: str) -> str:
    """
    Remove a feed from a userspace.

    Args:
        feed_id: The ID of the feed to delete.
        userspace: GUID of the userspace.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    existing = get_doc("feeds", feed_id)
    if not existing or extract_userspace(existing) != userspace:
        return ERROR_FEED_NOT_FOUND_OR_DENIED

    success, msg = delete_doc("feeds", feed_id)
    if success:
        return f"Feed {feed_id} deleted successfully from userspace {userspace}."
    else:
        return f"Error deleting feed: {msg}"


@mcp.tool()
@auth_required
def read_feed(url: str, userspace: str, limit: int = 20) -> str:
    """
    Fetch and process articles from a specific RSS feed URL.
    This triggers a live fetch and returns the latest articles.

    Args:
        url: The RSS feed URL to fetch
        userspace: GUID of the userspace.
        limit: Max number of articles to return (default: 20)
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    try:
        from tasks.article_processor import ArticleProcessor

        headers = {"User-Agent": "MoiraiBot/1.0"}
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            return f"Failed to fetch feed: HTTP {response.status_code}"

        processor = ArticleProcessor()

        feed_title, articles = processor.process_feed(url, response.text)

        # Store articles in background
        count = 0
        for article in articles:
            article["userspace"] = userspace  # Force userspace injection
            processor.store_article(article)
            count += 1

        # Return the latest few
        results = articles[:limit]

        output = [
            f"Feed: {feed_title}",
            f"Processed {len(articles)} articles, stored {count} in userspace {userspace}.",
        ]
        for a in results:
            output.append(
                f"- {a['title']} ({a['link']}) [{a.get('language', 'unknown')}]"
            )

        return "\n".join(output)

    except Exception as e:
        return f"Error reading feed: {e}"


@mcp.tool()
@auth_required
def update_feed_category(
    feed_id: str, new_category: str, userspace: str
) -> str:
    """
    Update the category of an existing feed.

    Args:
        feed_id: The ID of the feed to update.
        new_category: New category name.
        userspace: GUID of the userspace.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    existing = get_doc("feeds", feed_id)
    if not existing or extract_userspace(existing) != userspace:
        return ERROR_FEED_NOT_FOUND_OR_DENIED

    success, msg = update_doc("feeds", feed_id, {"category": new_category})
    if success:
        return f"Feed {feed_id} category updated to {new_category}."
    else:
        return f"Error updating feed: {msg}"
