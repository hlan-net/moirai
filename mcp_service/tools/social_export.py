"""
Social export MCP tool.

Allows agents to share Moirai Issues to Bluesky.
"""

import logging

from api.bluesky_ops import bluesky_uri_to_url, generate_bluesky_post_text, post_to_bluesky
from api.db import fetch_from_couchdb, query_couchdb, update_couchdb_doc_safe
from api.userspace_ops import get_userspace, resolve_llm_config
from mcp_service.core import mcp

from .userspace import extract_userspace, validate_userspace
from ..responses import (
    success,
    validation_error,
    not_found_error,
    transient_error,
    internal_error,
)

logger = logging.getLogger(__name__)


@mcp.tool()
def publish_to_bluesky(issue_id: str, userspace: str) -> dict:
    """Share a Moirai Issue to Bluesky.

    Fetches the issue and its linked articles, generates a post via the
    userspace LLM (<=300 chars), submits it via atproto, and records the
    post URI on the issue document.

    Returns:
        Standardized MCPResponse as dict.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    issue = fetch_from_couchdb("issues", issue_id)
    if not issue or extract_userspace(issue) != userspace:
        return not_found_error("issue", issue_id).to_dict()

    userspace_doc = get_userspace(userspace)
    if not userspace_doc:
        return not_found_error("userspace", userspace).to_dict()

    bluesky_handle = userspace_doc.get("bluesky_handle")
    bluesky_app_password = userspace_doc.get("bluesky_app_password")
    if not bluesky_handle or not bluesky_app_password:
        return validation_error(
            "Bluesky credentials not configured on this userspace."
        ).to_dict()

    # Fetch linked articles in a single bulk query
    premises = issue.get("premises") or []
    article_ids = [
        p.get("id") if isinstance(p, dict) else p
        for p in premises[:10]
        if (p.get("id") if isinstance(p, dict) else p)
    ]
    articles = (
        query_couchdb("articles", {"_id": {"$in": article_ids}})
        if article_ids
        else []
    )

    llm_config = resolve_llm_config(userspace)
    post_text = generate_bluesky_post_text(issue, articles, llm_config)

    try:
        post_uri = post_to_bluesky(bluesky_handle, bluesky_app_password, post_text)
    except Exception as exc:
        logger.error("Bluesky post failed for issue %s: %s", issue_id, exc)
        return transient_error(
            message=f"Bluesky post failed: {exc}",
            retry_after_ms=5000,
        ).to_dict()

    # Store post URI on the issue document
    social_posts = issue.get("social_posts") or {}
    social_posts["bluesky"] = post_uri
    update_couchdb_doc_safe("issues", issue_id, {"social_posts": social_posts})

    post_url = bluesky_uri_to_url(post_uri, bluesky_handle) or post_uri
    return success(
        data={
            "post_url": post_url,
            "post_uri": post_uri,
            "issue_id": issue_id,
        },
        message=f"Shared to Bluesky: {post_url}",
    ).to_dict()
