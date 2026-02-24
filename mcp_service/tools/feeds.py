import hashlib
import requests
from datetime import datetime, timezone
from ..core import mcp, auth_required, validate_userspace
from ..db import db_request, store_doc, get_doc, delete_doc, update_doc
from .constants import ERROR_FEED_NOT_FOUND_OR_DENIED
from .userspace import build_userspace_selector, extract_userspace, with_userspace

@mcp.tool()
@auth_required
def add_feed(
    url: str, title: str, userspace: str, category: str = "general"
) -> str:
    """
    Register a new RSS feed into a specific userspace.

    Args:
        url: The RSS feed URL.
        title: Human-readable title for the feed.
        userspace: GUID of the userspace.
        category: Optional category (e.g., 'tech', 'finance').
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

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
            return f"Feed already exists in userspace {userspace}."

        doc_id = store_doc("feeds", feed_doc)
        return f"Feed '{title}' added with ID: {doc_id} to userspace {userspace}"
    except Exception as e:
        return f"Error adding feed: {e}"


@mcp.tool()
@auth_required
def list_feeds(userspace: str) -> str:
    """
    List all RSS feeds registered in a specific userspace.

    Args:
        userspace: GUID of the userspace.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return err

    selector = build_userspace_selector(userspace)
    try:
        res = db_request(
            "POST", "feeds", path="/_find", json_data={"selector": selector}
        )
        if res.status_code != 200:
            return f"Error fetching feeds: {res.text}"

        docs = res.json().get("docs", [])
        feeds = []
        for doc in docs:
            feeds.append(
                f"ID: {doc['_id']}\nTitle: {doc['title']}\nURL: {doc['url']}\nCategory: {doc.get('category', 'N/A')}\n"
            )

        return (
            "\n---\n".join(feeds)
            if feeds
            else f"No feeds found in userspace {userspace}."
        )
    except Exception as e:
        return f"Error listing feeds: {e}"


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
