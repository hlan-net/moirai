"""Regenerate annotations that predate the current ANNOTATION_VERSION.

The AnnotationWorker only sees new articles on the changes feed and skips
documents that already carry ``annotations``, so a prompt or vocabulary
change never reaches existing articles. This script finds articles whose
``annotation_version`` is missing or older than the current one and
re-annotates them through the same backends the worker uses.

Run inside the worker pod (same env, same network):

    python -m scripts.reannotate_outdated --dry-run            # count only
    python -m scripts.reannotate_outdated --days 3 --limit 500
    python -m scripts.reannotate_outdated --userspace <uuid>
    python -m scripts.reannotate_outdated --limit 5000 --concurrency 2

The job is interruptible and resumable. Each finished article is stamped
with the current ``annotation_version`` as soon as it is stored and is never
listed again, so stopping the run (Ctrl-C, pod restart) loses at most the
articles in flight; the next run continues with exactly what is left. The
final summary names the remaining count, so no separate dry run is needed
between batches.

Articles expire after ARTICLE_EXPIRATION_DAYS anyway, so ``--days`` keeps
the run proportional to what readers will still see.
"""

import argparse
import logging
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Iterator

import requests

from api.db_config import get_couchdb_uri
from tasks.annotator import (
    ANNOTATION_ALL_SCOPE,
    ANNOTATION_DESIGN_DOC,
    ANNOTATION_VERSION,
    ANNOTATION_VERSION_VIEW,
    annotate_article,
    store_annotation,
)

logger = logging.getLogger("reannotate")

PAGE_SIZE = 100
DEFAULT_PROGRESS_EVERY = 25


def _cutoff(days: int | None) -> str | None:
    """ISO 8601 lower bound for ``published``, or None for no limit."""
    if days is None:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%S")


def outdated_selector(userspace: str | None, days: int | None = None) -> dict:
    """Mango selector for annotated articles behind ANNOTATION_VERSION.

    *days* limits the match to articles published in the last N days; the
    ``published`` field is ISO 8601, so a string comparison is enough.
    """
    selector: dict = {
        "annotations": {"$exists": True},
        "$or": [
            {"annotation_version": {"$exists": False}},
            {"annotation_version": {"$lt": ANNOTATION_VERSION}},
        ],
    }
    if userspace:
        selector["userspace"] = userspace
    cutoff = _cutoff(days)
    if cutoff is not None:
        selector["published"] = {"$gte": cutoff}
    return selector


def iter_outdated(
    userspace: str | None, limit: int, days: int | None = None
) -> Iterator[dict]:
    """Yield up to *limit* outdated article docs, paging with bookmarks."""
    url = f"{get_couchdb_uri()}articles/_find"
    bookmark = None
    yielded = 0
    while yielded < limit:
        body = {
            "selector": outdated_selector(userspace, days),
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


def _view_ranges(userspace: str | None, days: int | None) -> list[dict]:
    """Key ranges of the by_version view that together hold the outdated set.

    Keys are ``[scope, version, published]``. Missing versions are emitted as
    null, which sorts before every number, so the outdated set is the null
    range plus one range per integer version below the current one (the
    annotator only ever stores integers).
    """
    scope = userspace or ANNOTATION_ALL_SCOPE
    cutoff = _cutoff(days)
    ranges = []
    for version in [None, *range(ANNOTATION_VERSION)]:
        start = [scope, version] if cutoff is None else [scope, version, cutoff]
        ranges.append({"start_key": start, "end_key": [scope, version, {}]})
    return ranges


def count_outdated(userspace: str | None, days: int | None = None) -> int:
    """Number of outdated articles, from the by_version reduce view.

    A few reduce queries instead of a full listing: seconds rather than
    minutes on a large database. Falls back to an id-only Mango scan when the
    view does not exist yet (database not initialised by this version).
    """
    url = (
        f"{get_couchdb_uri()}articles/_design/{ANNOTATION_DESIGN_DOC}"
        f"/_view/{ANNOTATION_VERSION_VIEW}/queries"
    )
    # The first query after deploy builds the index, which can take a while.
    res = requests.post(
        url, json={"queries": _view_ranges(userspace, days)}, timeout=600
    )
    if res.status_code == 404:
        logger.warning("view %s missing, counting with a full scan", url)
        return _count_by_scan(userspace, days)
    res.raise_for_status()
    total = 0
    for result in res.json().get("results", []):
        rows = result.get("rows", [])
        total += rows[0]["value"] if rows else 0
    return total


def _count_by_scan(userspace: str | None, days: int | None) -> int:
    url = f"{get_couchdb_uri()}articles/_find"
    total = 0
    bookmark = None
    while True:
        body = {
            "selector": outdated_selector(userspace, days),
            "fields": ["_id"],
            "limit": 5000,
        }
        if bookmark:
            body["bookmark"] = bookmark
        res = requests.post(url, json=body, timeout=600)
        res.raise_for_status()
        data = res.json()
        docs = data.get("docs", [])
        if not docs:
            return total
        total += len(docs)
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


def _duration(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


@dataclass
class Progress:
    """Counts finished articles and logs ``done/total, rate, ETA`` lines."""

    total: int
    every: int
    done: int = 0
    failed: int = 0
    started: float = field(default_factory=time.monotonic)

    @property
    def finished(self) -> int:
        return self.done + self.failed

    def record(self, ok: bool) -> None:
        if ok:
            self.done += 1
        else:
            self.failed += 1
        if self.every and self.finished % self.every == 0:
            logger.info("progress %s", self.line())

    def line(self) -> str:
        elapsed = time.monotonic() - self.started
        pct = 100.0 * self.finished / self.total if self.total else 100.0
        text = (
            f"{self.finished}/{self.total} ({pct:.1f}%), "
            f"{self.failed} failed, elapsed {_duration(elapsed)}"
        )
        if self.finished:
            rate = elapsed / self.finished
            left = max(self.total - self.finished, 0)
            text += f", {rate:.2f} s/article"
            if left:
                text += f", ETA {_duration(rate * left)}"
        return text


def _reannotate_isolated(doc: dict, dry_run: bool) -> bool:
    """reannotate() that reports an unexpected exception as a failure."""
    try:
        return reannotate(doc, dry_run)
    except Exception:  # noqa: BLE001 - one article must not stop the run
        logger.exception("re-annotation of %s raised", doc.get("_id"))
        return False


def run(
    docs: Iterable[dict],
    progress: Progress,
    concurrency: int = 1,
    dry_run: bool = False,
) -> bool:
    """Re-annotate *docs* with at most *concurrency* articles in flight.

    Returns False when interrupted. A failing article is counted and does not
    stop the others. On KeyboardInterrupt the articles already in flight are
    allowed to finish (and be stored) before returning.
    """
    if concurrency <= 1:
        try:
            for doc in docs:
                progress.record(_reannotate_isolated(doc, dry_run))
        except KeyboardInterrupt:
            return False
        return True

    in_flight: set[Future] = set()

    def collect(futures: set[Future]) -> None:
        for fut in futures:
            progress.record(fut.result())

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        try:
            for doc in docs:
                if len(in_flight) >= concurrency:
                    finished, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)
                    collect(finished)
                in_flight.add(pool.submit(_reannotate_isolated, doc, dry_run))
            collect(set(wait(in_flight).done))
        except KeyboardInterrupt:
            logger.warning(
                "interrupted, letting %d in-flight article(s) finish", len(in_flight)
            )
            collect(set(wait(in_flight).done))
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--userspace", help="restrict to one userspace UUID")
    parser.add_argument("--limit", type=int, default=100, help="max articles")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="only articles published in the last N days (0 = no limit)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only report how many articles are outdated (add --list for ids)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="with --dry-run, also list up to --limit outdated articles",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="articles annotated in parallel (default 1). Raise carefully: "
        "each in-flight article is one request to the annotation backend",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        help="log done/total, rate and ETA every N articles (0 = off)",
    )
    args = parser.parse_args(argv)
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    days = args.days if args.days > 0 else None
    scope = f"userspace {args.userspace}" if args.userspace else "all userspaces"
    window = f"last {days} days" if days else "no age limit"
    outdated = count_outdated(args.userspace, days)
    logger.info(
        "%d article(s) behind version %d (%s, %s)",
        outdated,
        ANNOTATION_VERSION,
        scope,
        window,
    )
    if args.dry_run and not args.list:
        return 0

    progress = Progress(total=min(outdated, args.limit), every=args.progress_every)
    completed = run(
        iter_outdated(args.userspace, args.limit, days),
        progress,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        logger.info("listed %d article(s)", progress.done)
        return 0

    remaining = count_outdated(args.userspace, days)
    logger.info(
        "%s: %s. %d article(s) still behind version %d (%s, %s). Finished "
        "articles are stamped and never revisited: re-run to continue.",
        "done" if completed else "stopped",
        progress.line(),
        remaining,
        ANNOTATION_VERSION,
        scope,
        window,
    )
    if not completed:
        return 130
    return 1 if progress.failed and not progress.done else 0


if __name__ == "__main__":
    sys.exit(main())
