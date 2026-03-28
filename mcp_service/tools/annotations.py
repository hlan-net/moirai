"""MCP tools for managing AI article annotations.

Provides tools to:
- re-annotate a specific article
- list unannotated articles in a userspace
- get annotation statistics for a userspace
"""

from ..core import mcp, auth_required, validate_userspace
from ..db import db_request
from .userspace import build_userspace_selector
from tasks.annotator import annotate_article, store_annotation
from ..responses import (
    success,
    validation_error,
    not_found_error,
    transient_error,
    internal_error,
)

# Database name
ARTICLES_DB = "articles"


@mcp.tool()
@auth_required
def reannotate_article(article_id: str, userspace: str) -> dict:
    """
    Re-run AI annotation on a specific article, overwriting any existing annotation.

    Returns:
        Standardized MCPResponse as dict.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    if not article_id.strip():
        return validation_error("article_id cannot be empty").to_dict()

    try:
        # Fetch the article
        resp = db_request("GET", ARTICLES_DB, path=f"/{article_id}")
        if resp.status_code == 404:
            return not_found_error("article", article_id).to_dict()
        if resp.status_code >= 500:
            return transient_error(
                message=f"Database error fetching article: HTTP {resp.status_code}",
                retry_after_ms=2000,
            ).to_dict()
        if resp.status_code != 200:
            return internal_error(
                message=f"Failed to fetch article: {resp.text}"
            ).to_dict()

        doc = resp.json()

        title = doc.get("title", "")
        summary = doc.get("summary", "") or doc.get("description", "")

        if not title:
            return validation_error(
                "Article has no title — cannot annotate"
            ).to_dict()

        annotation = annotate_article(title, summary)
        if annotation is None:
            return internal_error(
                message="Annotation failed — LLM returned invalid result"
            ).to_dict()

        stored = store_annotation(article_id, annotation)
        if not stored:
            return transient_error(
                message="Failed to store annotation in CouchDB",
                retry_after_ms=2000,
            ).to_dict()

        return success(
            data={
                "article_id": article_id,
                "annotation": annotation,
            },
            message=f"Article {article_id} re-annotated successfully",
        ).to_dict()

    except Exception as e:
        return internal_error(
            message=f"Annotation error: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def list_unannotated_articles(userspace: str, limit: int = 50) -> dict:
    """
    List articles in a userspace that have not yet been annotated by AI.

    Returns:
        Standardized MCPResponse as dict.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    limit = min(limit, 200)

    selector = {
        "$and": [
            build_userspace_selector(userspace),
            {
                "$or": [
                    {"annotations": {"$exists": False}},
                    {"annotations": None},
                ]
            },
        ]
    }

    try:
        query_payload = {
            "selector": selector,
            "limit": limit,
            "fields": ["_id", "title", "published", "feed_title"],
        }

        resp = db_request("POST", ARTICLES_DB, "/_find", json_data=query_payload)

        if resp.status_code >= 500:
            return transient_error(
                message=f"Database error querying articles: HTTP {resp.status_code}",
                retry_after_ms=2000,
            ).to_dict()

        if resp.status_code != 200:
            return internal_error(
                message=f"Query failed: {resp.text}"
            ).to_dict()

        docs = resp.json().get("docs", [])
        results = [
            {
                "_id": d.get("_id"),
                "title": d.get("title", "Untitled"),
                "published": d.get("published", ""),
                "feed_title": d.get("feed_title", ""),
            }
            for d in docs
        ]

        return success(
            data={
                "articles": results,
                "count": len(results),
                "userspace": userspace,
            },
            message=f"Found {len(results)} unannotated article(s)",
        ).to_dict()

    except Exception as e:
        return internal_error(
            message=f"Query execution error: {str(e)}"
        ).to_dict()


@mcp.tool()
@auth_required
def get_annotation_stats(userspace: str) -> dict:
    """
    Get annotation statistics for a userspace: total articles, annotated count,
    and breakdowns by priority and sentiment.

    Returns:
        Standardized MCPResponse as dict.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return validation_error(f"Invalid userspace: {err}").to_dict()

    try:
        # Count annotated articles
        annotated_payload = {
            "selector": {
                "$and": [
                    build_userspace_selector(userspace),
                    {"annotations": {"$exists": True}},
                    {"annotations": {"$ne": None}},
                ]
            },
            "limit": 500,
            "fields": ["_id", "annotations"],
        }
        annotated_resp = db_request(
            "POST", ARTICLES_DB, "/_find", json_data=annotated_payload
        )

        if annotated_resp.status_code >= 500:
            return transient_error(
                message=f"Database error querying stats: HTTP {annotated_resp.status_code}",
                retry_after_ms=2000,
            ).to_dict()

        if annotated_resp.status_code != 200:
            return internal_error(
                message=f"Query failed: {annotated_resp.text}"
            ).to_dict()

        annotated_docs = annotated_resp.json().get("docs", [])
        annotated_count = len(annotated_docs)

        # Build breakdowns
        priority_counts = {"low": 0, "medium": 0, "high": 0}
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        topic_counts: dict[str, int] = {}

        for doc in annotated_docs:
            ann = doc.get("annotations", {})
            if not isinstance(ann, dict):
                continue

            p = ann.get("priority", "")
            if p in priority_counts:
                priority_counts[p] += 1

            s = ann.get("sentiment", "")
            if s in sentiment_counts:
                sentiment_counts[s] += 1

            for t in ann.get("topics", []):
                topic_counts[t] = topic_counts.get(t, 0) + 1

        # Sort topics by count descending
        top_topics = sorted(
            topic_counts.items(), key=lambda x: x[1], reverse=True
        )[:20]

        return success(
            data={
                "userspace": userspace,
                "annotated_count": annotated_count,
                "priority": priority_counts,
                "sentiment": sentiment_counts,
                "top_topics": [
                    {"topic": t, "count": c} for t, c in top_topics
                ],
            },
            message=f"Annotation stats: {annotated_count} annotated articles",
        ).to_dict()

    except Exception as e:
        return internal_error(
            message=f"Stats execution error: {str(e)}"
        ).to_dict()
