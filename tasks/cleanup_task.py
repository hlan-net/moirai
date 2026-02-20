import os
import time
import requests
import datetime
import threading
import logging
from urllib.parse import quote
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.db_config import get_couchdb_uri

logger = logging.getLogger(__name__)


def get_all_docs(db_name):
    try:
        url = f"{get_couchdb_uri()}{db_name}/_all_docs?include_docs=true"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return [row["doc"] for row in res.json().get("rows", [])]
    except Exception as e:
        logger.error(f"Cleanup: Error fetching {db_name}: {e}")
    return []


def delete_doc(db_name, doc_id, rev):
    try:
        # Construct proper CouchDB delete URL: /db/doc_id?rev=REV
        safe_db = quote(db_name, safe="")
        safe_id = quote(doc_id, safe="")
        url = f"{get_couchdb_uri()}{safe_db}/{safe_id}?rev={rev}"
        res = requests.delete(url, timeout=10)
        return res.status_code in (200, 202)
    except Exception as e:
        logger.error(f"Cleanup: Error deleting {doc_id} from {db_name}: {e}")
    return False


def parse_date(date_str):
    if not date_str:
        return datetime.datetime.now(datetime.timezone.utc)
    # Handle various formats or fallback
    try:
        # ISO format
        return datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    return datetime.datetime.now(datetime.timezone.utc)


def _iter_premises(doc):
    premises = doc.get("premises")
    if isinstance(premises, list):
        return premises
    return []


def _collect_linked_issue_ids(issues):
    linked_issue_ids = set()
    for issue in issues:
        if issue.get("type") != "issue":
            continue
        if issue.get("longevity") != "temporal":
            continue
        for premise in _iter_premises(issue):
            if premise.get("type") in {"issue", "event", "trend"}:
                issue_id = premise.get("id")
                if isinstance(issue_id, str):
                    linked_issue_ids.add(issue_id)
    return linked_issue_ids


def _collect_article_links(issue):
    links = set()
    if isinstance(issue.get("article_links"), list):
        links.update(issue["article_links"])
    for premise in _iter_premises(issue):
        if premise.get("type") in {"message", "article", "link"}:
            link = premise.get("id")
            if isinstance(link, str):
                links.add(link)
    return links


def run_cleanup():
    logger.info("Cleanup: Starting maintenance cycle...")

    now = datetime.datetime.now(datetime.timezone.utc)

    issues = get_all_docs("issues")
    linked_issue_ids = _collect_linked_issue_ids(issues)

    logger.info(
        "Cleanup: Found %s temporal issues referencing %s transient issues.",
        len([i for i in issues if i.get("longevity") == "temporal"]),
        len(linked_issue_ids),
    )

    active_article_links = set()
    issues_deleted = 0
    issues_kept = 0

    for issue in issues:
        if issue.get("type") != "issue":
            continue

        issue_id = issue.get("_id")
        longevity = issue.get("longevity")
        status = issue.get("status")

        if longevity != "transient":
            issues_kept += 1
            active_article_links.update(_collect_article_links(issue))
            continue

        created_at = issue.get("born_at") or issue.get("created_at")
        dt = parse_date(created_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        age = now - dt

        should_delete = (
            issue_id not in linked_issue_ids
            and age.days > 365
            and status != "eternal"
        )

        if should_delete:
            logger.info(
                "Cleanup: Deleting orphaned transient issue %s (Age: %s days)",
                issue_id,
                age.days,
            )
            if delete_doc("issues", issue_id, issue.get("_rev")):
                issues_deleted += 1
        else:
            issues_kept += 1
            active_article_links.update(_collect_article_links(issue))

    logger.info(
        "Cleanup: Issues processed. Deleted: %s. Kept: %s. Active referenced articles: %s",
        issues_deleted,
        issues_kept,
        len(active_article_links),
    )

    articles = get_all_docs("articles")
    articles_deleted = 0

    for article in articles:
        link = article.get("link")
        article_id = article.get("_id")
        published = article.get("published")

        dt = parse_date(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        age = now - dt

        should_delete = link not in active_article_links and age.days > 30
        if should_delete:
            logger.info(
                "Cleanup: Deleting orphaned article %s (Age: %s days)",
                article_id,
                age.days,
            )
            if delete_doc("articles", article_id, article.get("_rev")):
                articles_deleted += 1

    logger.info(
        "Cleanup: Finished. Deleted %s issues and %s articles.",
        issues_deleted,
        articles_deleted,
    )


class CleanupTask(threading.Thread):
    def __init__(self, interval=86400):  # Default 24 hours
        threading.Thread.__init__(self)
        self.interval = interval
        self.daemon = True

    def run(self):
        while True:
            try:
                run_cleanup()
            except Exception as e:
                logger.error(f"Cleanup: Unexpected error in loop: {e}")
            time.sleep(self.interval)
