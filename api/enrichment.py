import logging
from api.db import query_couchdb, fetch_from_couchdb
from api.db_constants import MONGO_ELEM_MATCH, MONGO_IN

logger = logging.getLogger(__name__)


def enrich_articles_with_issues(articles):
    """
    Enriches a list of articles with their associated issues.
    Expected article format: dictionary with 'link' and 'feed_url' fields.
    """
    if not articles:
        return articles

    article_links = [a.get("link") for a in articles if a.get("link")]
    if not article_links:
        return articles

    issues, feeds = _fetch_related_data(article_links)

    article_issue_map, feed_title_map, feed_favicon_map = (
        _build_mappings(issues, feeds)
    )

    _apply_enrichment(
        articles,
        article_issue_map,
        feed_title_map,
        feed_favicon_map,
    )

    return articles


def _fetch_related_data(article_links):
    """Fetches issues and feeds based on article links."""
    # Batch fetch issues containing these article links in premises
    issues = []
    if article_links:
        issues = query_couchdb(
            "issues",
            selector={"premises": {MONGO_ELEM_MATCH: { "id": {MONGO_IN: article_links} }}},
            limit=1000,
        )

    # Pre-fetch feed info for title and favicon mapping
    feeds = fetch_from_couchdb("feeds")
    return issues, feeds


def _build_mappings(issues, feeds):
    """Builds lookup maps for enrichment."""
    feed_title_map = {
        feed.get("url"): feed.get("title") for feed in feeds if feed.get("url")
    }
    feed_favicon_map = {
        feed.get("url"): feed.get("favicon_url") for feed in feeds if feed.get("url")
    }

    # Build article link to issue logos and IDs mapping
    article_issue_map = {}

    for issue in issues:
        issue_id = issue.get("_id")
        issue_logos = issue.get("logos")
        if not issue_logos:
            continue

        for premise in issue.get("premises", []):
            if premise.get("type") == "message":
                link = premise.get("id")
                if link:
                    # Map link -> issue summary info
                    article_issue_map.setdefault(link, []).append({
                        "id": issue_id,
                        "logos": issue_logos,
                        "longevity": issue.get("longevity"),
                        "status": issue.get("status")
                    })

    return article_issue_map, feed_title_map, feed_favicon_map


def _apply_enrichment(
    articles,
    article_issue_map,
    feed_title_map,
    feed_favicon_map,
):
    """Applies the enrichment data to the articles list in-place."""
    for article in articles:
        _enrich_article_feed(article, feed_title_map, feed_favicon_map)
        _enrich_article_issues(article, article_issue_map)


def _enrich_article_feed(article, feed_title_map, feed_favicon_map):
    """Enriches a single article with feed-specific info."""
    feed_url = article.get("feed_url")
    if feed_url:
        article["feed_title"] = feed_title_map.get(feed_url)
        favicon = feed_favicon_map.get(feed_url)
        if favicon:
            article["feed_favicon"] = favicon


def _enrich_article_issues(article, article_issue_map):
    """Enriches a single article with associated issues."""
    article_link = article.get("link")
    if article_link and article_link in article_issue_map:
        article["issues"] = article_issue_map[article_link]


def enrich_issues_with_constituents(issues, recursive=True):
    """
    Enriches a list of issues with their full premise objects (articles or nested issues).
    """
    if not issues:
        return issues

    for issue in issues:
        premises = issue.get("premises", [])
        enriched_premises = []
        for premise in premises:
            doc = _fetch_premise_doc(premise, recursive)
            if doc:
                enriched_premises.append(doc)
        
        issue["enriched_premises"] = enriched_premises
    return issues


def _fetch_premise_doc(premise, recursive):
    """Helper to fetch a single premise document from CouchDB."""
    p_type = premise.get("type")
    p_id = premise.get("id")
    if not p_id:
        return None

    try:
        if p_type == "message":
            return fetch_from_couchdb("articles", p_id)
        elif p_type == "issue":
            doc = fetch_from_couchdb("issues", p_id)
            if doc and recursive:
                enrich_issues_with_constituents([doc], recursive=True)
            return doc
    except Exception as e:
        logger.warning(f"Could not fetch premise {p_id} of type {p_type}: {e}")
    
    return None
