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
MAX_CONFLICT_RETRIES = 3


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


def _bulk_write(docs: list[dict]) -> tuple[int, list[str], list[str]]:
    """Write ``docs`` with ``_bulk_docs``.

    Returns ``(accepted, conflicted_ids, failed_ids)``. ``_bulk_docs`` answers
    201 even when individual documents are rejected, so every result row is
    checked: a ``conflict`` (another writer, e.g. the annotation worker,
    updated the article after this page was read) is retryable, anything else
    is a hard failure.
    """
    url = f"{get_couchdb_uri()}articles/_bulk_docs"
    res = requests.post(url, json={"docs": docs}, timeout=60)
    res.raise_for_status()
    accepted = 0
    conflicted: list[str] = []
    failed: list[str] = []
    for result in res.json():
        if result.get("ok"):
            accepted += 1
        elif result.get("error") == "conflict":
            conflicted.append(result.get("id"))
        else:
            logger.warning(
                "Backfill: %s rejected: %s %s",
                result.get("id"),
                result.get("error"),
                result.get("reason"),
            )
            failed.append(result.get("id"))
    return accepted, conflicted, failed


def _fetch_docs(ids: list[str]) -> list[dict]:
    """Fetch the current revision of ``ids``; deleted or missing ids are dropped."""
    url = f"{get_couchdb_uri()}articles/_all_docs"
    res = requests.post(
        url, params={"include_docs": "true"}, json={"keys": ids}, timeout=60
    )
    res.raise_for_status()
    return [row["doc"] for row in res.json().get("rows", []) if row.get("doc")]


def _apply_section(
    doc: dict, feed_categories: dict[str, str], recompute_all: bool
) -> tuple[str, str] | None:
    """Set ``section``/``section_source`` on ``doc`` if it needs one.

    Returns the assigned ``(section, source)``, or ``None`` when the doc is
    left untouched (already sectioned, or already up to date).
    """
    if not recompute_all and doc.get("section"):
        return None
    section, source = section_for(doc, feed_categories)
    if doc.get("section") == section and doc.get("section_source") == source:
        return None
    doc["section"] = section
    doc["section_source"] = source
    return section, source


def _write_with_retry(
    docs: list[dict], feed_categories: dict[str, str], recompute_all: bool
) -> tuple[int, int]:
    """Write ``docs``, re-reading and retrying conflicted ones.

    Returns ``(written, failed)``. A conflicted article is re-fetched with its
    fresh ``_rev`` and its section recomputed; if the concurrent writer already
    gave it a section, nothing more is written for it.
    """
    written = 0
    failed = 0
    pending = docs
    for attempt in range(MAX_CONFLICT_RETRIES + 1):
        accepted, conflicted, hard_failed = _bulk_write(pending)
        written += accepted
        failed += len(hard_failed)
        if not conflicted:
            break
        if attempt == MAX_CONFLICT_RETRIES:
            logger.warning(
                "Backfill: %d articles still conflicted after %d retries: %s",
                len(conflicted),
                MAX_CONFLICT_RETRIES,
                conflicted,
            )
            failed += len(conflicted)
            break
        logger.info("Backfill: retrying %d conflicted articles", len(conflicted))
        pending = [
            doc
            for doc in _fetch_docs(conflicted)
            if _apply_section(doc, feed_categories, recompute_all)
        ]
        if not pending:
            break
    return written, failed


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
    failed = 0
    by_section: Counter[str] = Counter()
    by_source: Counter[str] = Counter()

    for page in _iter_article_pages():
        seen += len(page)
        updates: list[dict] = []
        for doc in page:
            assigned = _apply_section(doc, feed_categories, recompute_all)
            if assigned is None:
                continue
            section, source = assigned
            by_section[section] += 1
            by_source[source] += 1
            updates.append(doc)
        changed += len(updates)
        if updates and not dry_run:
            page_written, page_failed = _write_with_retry(
                updates, feed_categories, recompute_all
            )
            written += page_written
            failed += page_failed
        logger.info(
            "Backfill: seen %d, to update %d, written %d, failed %d",
            seen,
            changed,
            written,
            failed,
        )

    if written and not dry_run:
        _invalidate_stream_cache()

    summary = {
        "seen": seen,
        "changed": changed,
        "written": written,
        "failed": failed,
    }
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
        summary = run(recompute_all=args.all, dry_run=args.dry_run)
    except requests.exceptions.RequestException as e:
        logger.error("Backfill: CouchDB request failed: %s", e)
        return 1
    if summary["failed"]:
        logger.error(
            "Backfill: %d articles were not written; re-run to retry them",
            summary["failed"],
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
