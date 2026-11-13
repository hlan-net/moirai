"""Assign a stream ``section`` to articles that predate sectioning (#266).

New articles get their section at ingestion. This one-off backfill walks the
``articles`` database in pages (never one request: see #288), computes the
section from the same signals the ingestion path uses (feed category, URL,
annotation topic, default) and writes it back with ``_bulk_docs``.

Run inside the worker or API pod (same env, same network):

    python -m scripts.backfill_sections --dry-run     # count only
    python -m scripts.backfill_sections               # articles without a section
    python -m scripts.backfill_sections --all         # recompute every article,
                                                      # e.g. after changing a
                                                      # feed's category

Interruptible and resumable: every page is written as soon as it is computed,
and the default mode only lists articles that still lack a section.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from typing import Iterator

import requests

from api.db_config import get_couchdb_uri
from tasks.sections import STREAM_CACHE_KEYS, resolve_section

logger = logging.getLogger("backfill_sections")

PAGE_SIZE = 500


def _iter_article_pages(page_size: int = PAGE_SIZE) -> Iterator[list[dict]]:
    """Yield pages of article docs from ``_all_docs`` without loading the DB."""
    url = f"{get_couchdb_uri()}articles/_all_docs"
    start_key = None
    while True:
        params: dict[str, object] = {"include_docs": "true", "limit": page_size}
        if start_key is not None:
            params["startkey"] = json.dumps(start_key)
        res = requests.get(url, params=params, timeout=60)
        res.raise_for_status()
        rows = res.json().get("rows", [])
        docs = [
            row["doc"]
            for row in rows
            if row.get("doc")
            and row["id"] != start_key
            and not row["id"].startswith("_design/")
        ]
        if docs:
            yield docs
        if len(rows) < page_size or rows[-1]["id"] == start_key:
            return
        start_key = rows[-1]["id"]


def load_feed_categories() -> dict[str, str]:
    """Map feed URL (current and original) to its ``category``."""
    url = f"{get_couchdb_uri()}feeds/_all_docs"
    res = requests.get(url, params={"include_docs": "true"}, timeout=30)
    res.raise_for_status()
    categories: dict[str, str] = {}
    for row in res.json().get("rows", []):
        doc = row.get("doc") or {}
        category = doc.get("category")
        if not category:
            continue
        for key in ("url", "original_url"):
            if doc.get(key):
                categories[doc[key]] = category
    return categories


def section_for(doc: dict, feed_categories: dict[str, str]) -> tuple[str, str]:
    topics = (doc.get("annotations") or {}).get("topics")
    return resolve_section(
        feed_categories.get(doc.get("feed_url", "")), doc.get("link"), topics
    )


def _bulk_update(docs: list[dict]) -> int:
    """Write ``docs`` with ``_bulk_docs``; returns the number of accepted writes."""
    url = f"{get_couchdb_uri()}articles/_bulk_docs"
    res = requests.post(url, json={"docs": docs}, timeout=60)
    res.raise_for_status()
    accepted = 0
    for result in res.json():
        if result.get("ok"):
            accepted += 1
        else:
            logger.warning(
                "Backfill: %s rejected: %s %s",
                result.get("id"),
                result.get("error"),
                result.get("reason"),
            )
    return accepted


def _invalidate_stream_cache() -> None:
    try:
        from api.extensions import get_redis_client

        redis_client = get_redis_client()
        if redis_client:
            redis_client.delete(*STREAM_CACHE_KEYS)
    except Exception as e:  # cache only
        logger.warning("Backfill: could not invalidate Redis stream cache: %s", e)


def run(recompute_all: bool, dry_run: bool) -> dict[str, int]:
    feed_categories = load_feed_categories()
    logger.info("Backfill: %d feed URLs carry a category", len(feed_categories))

    seen = 0
    changed = 0
    written = 0
    by_section: Counter[str] = Counter()
    by_source: Counter[str] = Counter()

    for page in _iter_article_pages():
        seen += len(page)
        updates: list[dict] = []
        for doc in page:
            if not recompute_all and doc.get("section"):
                continue
            section, source = section_for(doc, feed_categories)
            if doc.get("section") == section and doc.get("section_source") == source:
                continue
            doc["section"] = section
            doc["section_source"] = source
            by_section[section] += 1
            by_source[source] += 1
            updates.append(doc)
        changed += len(updates)
        if updates and not dry_run:
            written += _bulk_update(updates)
        logger.info(
            "Backfill: seen %d, to update %d, written %d", seen, changed, written
        )

    if written and not dry_run:
        _invalidate_stream_cache()

    summary = {"seen": seen, "changed": changed, "written": written}
    logger.info("Backfill summary: %s", summary)
    logger.info("By section: %s", dict(by_section))
    logger.info("By source: %s", dict(by_source))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--all",
        action="store_true",
        help="recompute every article, not only those without a section",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="count and report, write nothing"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    try:
        run(recompute_all=args.all, dry_run=args.dry_run)
    except requests.exceptions.RequestException as e:
        logger.error("Backfill: CouchDB request failed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
