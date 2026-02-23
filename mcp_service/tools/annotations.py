"""MCP tools for managing AI article annotations.

Provides tools to:
- re-annotate a specific article
- list unannotated articles in a userspace
- get annotation statistics for a userspace
"""

import json
from ..core import mcp, auth_required, validate_userspace
from ..db import db_request
from .userspace import build_userspace_selector
from tasks.annotator import annotate_article, store_annotation

# Database name
ARTICLES_DB = "articles"


@mcp.tool()
@auth_required
def reannotate_article(
    article_id: str,
    userspace: str,
    api_key: str = None,
) -> str:
    """
    Re-run AI annotation on a specific article, overwriting any existing annotation.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return json.dumps({"error": err})

    if not article_id.strip():
        return json.dumps({"error": "article_id cannot be empty"})

    # Fetch the article
    resp = db_request("GET", ARTICLES_DB, path=f"/{article_id}")
    if resp.status_code == 404:
        return json.dumps({"error": f"Article {article_id} not found"})
    if resp.status_code != 200:
        return json.dumps({"error": f"Failed to fetch article: {resp.text}"})

    doc = resp.json()

    title = doc.get("title", "")
    summary = doc.get("summary", "") or doc.get("description", "")

    if not title:
        return json.dumps({"error": "Article has no title — cannot annotate"})

    annotation = annotate_article(title, summary)
    if annotation is None:
        return json.dumps({"error": "Annotation failed — LLM returned invalid result"})

    success = store_annotation(article_id, annotation)
    if not success:
        return json.dumps({"error": "Failed to store annotation in CouchDB"})

    return json.dumps(
        {
            "status": "ok",
            "article_id": article_id,
            "annotation": annotation,
        },
        indent=2,
    )


@mcp.tool()
@auth_required
def list_unannotated_articles(
    userspace: str,
    limit: int = 50,
    api_key: str = None,
) -> str:
    """
    List articles in a userspace that have not yet been annotated by AI.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return json.dumps({"error": err})

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

        if resp.status_code != 200:
            return json.dumps({"error": f"Query failed: {resp.text}"})

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

        return json.dumps(
            {"total": len(results), "userspace": userspace, "results": results},
            indent=2,
        )

    except Exception as e:
        return json.dumps({"error": f"Query execution error: {str(e)}"})


@mcp.tool()
@auth_required
def get_annotation_stats(
    userspace: str,
    api_key: str = None,
) -> str:
    """
    Get annotation statistics for a userspace: total articles, annotated count,
    and breakdowns by priority and sentiment.
    """
    valid, err = validate_userspace(userspace)
    if not valid:
        return json.dumps({"error": err})

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

        if annotated_resp.status_code != 200:
            return json.dumps({"error": f"Query failed: {annotated_resp.text}"})

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
        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[
            :20
        ]

        return json.dumps(
            {
                "userspace": userspace,
                "annotated_count": annotated_count,
                "priority": priority_counts,
                "sentiment": sentiment_counts,
                "top_topics": [{"topic": t, "count": c} for t, c in top_topics],
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"error": f"Stats execution error: {str(e)}"})
