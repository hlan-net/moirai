"""Regenerate annotations that predate the current ANNOTATION_VERSION.

The AnnotationWorker only sees new articles on the changes feed and skips
documents that already carry ``annotations``, so a prompt or vocabulary
change never reaches existing articles. This script finds articles whose
``annotation_version`` is missing or older than the current one and
re-annotates them through the same backends the worker uses.

Run inside the worker pod (same env, same network):

    python scripts/reannotate_outdated.py --dry-run
    python scripts/reannotate_outdated.py --userspace <uuid> --limit 200
"""

import argparse
import logging
import sys
from typing import Iterator

import requests

from api.db_config import get_couchdb_uri
from tasks.annotator import ANNOTATION_VERSION, annotate_article, store_annotation

logger = logging.getLogger("reannotate")

PAGE_SIZE = 100


def outdated_selector(userspace: str | None) -> dict:
    """Mango selector for annotated articles behind ANNOTATION_VERSION."""
    selector: dict = {
        "annotations": {"$exists": True},
        "$or": [
            {"annotation_version": {"$exists": False}},
            {"annotation_version": {"$lt": ANNOTATION_VERSION}},
        ],
    }
    if userspace:
        selector["userspace"] = userspace
    return selector


def iter_outdated(userspace: str | None, limit: int) -> Iterator[dict]:
    """Yield up to *limit* outdated article docs, paging with bookmarks."""
    url = f"{get_couchdb_uri()}articles/_find"
    bookmark = None
    yielded = 0
    while yielded < limit:
        body = {
            "selector": outdated_selector(userspace),
            "fields": ["_id", "title", "summary", "description", "language"],
            "limit": min(PAGE_SIZE, limit - yielded),
        }
        if bookmark:
            body["bookmark"] = bookmark
        res = requests.post(url, json=body, timeout=60)
        res.raise_for_status()
        data = res.json()
        docs = data.get("docs", [])
        if not docs:
            return
        for doc in docs:
            yield doc
            yielded += 1
        bookmark = data.get("bookmark")


def reannotate(doc: dict, dry_run: bool) -> bool:
    title = doc.get("title", "")
    if not title:
        return False
    if dry_run:
        logger.info("would re-annotate %s: %s", doc["_id"], title[:80])
        return True
    summary = doc.get("summary", "") or doc.get("description", "")
    annotation = annotate_article(title, summary, language=doc.get("language"))
    if annotation is None:
        logger.warning("annotation failed for %s: %s", doc["_id"], title[:80])
        return False
    if not store_annotation(doc["_id"], annotation):
        return False
    logger.info("%s: %s -> %s", doc["_id"], title[:60], annotation["topics"])
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--userspace", help="restrict to one userspace UUID")
    parser.add_argument("--limit", type=int, default=100, help="max articles")
    parser.add_argument("--dry-run", action="store_true", help="only list")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    done = failed = 0
    for doc in iter_outdated(args.userspace, args.limit):
        if reannotate(doc, args.dry_run):
            done += 1
        else:
            failed += 1
    logger.info(
        "%s %d article(s), %d failed (target version %d)",
        "listed" if args.dry_run else "re-annotated",
        done,
        failed,
        ANNOTATION_VERSION,
    )
    return 1 if failed and not done else 0


if __name__ == "__main__":
    sys.exit(main())
