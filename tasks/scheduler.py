from concurrent.futures import ThreadPoolExecutor
import logging
import os
import threading
import time

import requests

from api.db_config import get_couchdb_uri
from .fetch_feed_task import FetchFeedTask
from .scheduler_log import add_scheduler_log

logger = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = 4


def _max_workers() -> int:
    raw = os.environ.get("SCHEDULER_MAX_WORKERS", "").strip()
    if not raw:
        return DEFAULT_MAX_WORKERS
    try:
        return max(1, int(raw))
    except ValueError:
        logger.warning(
            "Invalid SCHEDULER_MAX_WORKERS=%r; using %d", raw, DEFAULT_MAX_WORKERS
        )
        return DEFAULT_MAX_WORKERS


def get_dynamic_interval(default_interval: int) -> int:
    db_url = get_couchdb_uri()
    try:
        res = requests.get(f"{db_url}config/main", timeout=2)
        if res.status_code == 200:
            config = res.json()
            return int(config.get("iteration_interval", default_interval))
    except Exception:
        pass
    return default_interval


def _run_feed_task(
    feed_id: str,
    url: str,
    original_url: str,
    etag: str | None = None,
    last_modified: str | None = None,
) -> None:
    FetchFeedTask(
        feed_id,
        url,
        original_url,
        etag=etag,
        last_modified=last_modified,
    ).fetch_url()


def _process_feeds(feeds_db_url: str) -> dict:
    """Fetch and trigger feed tasks with bounded concurrency."""
    try:
        response = requests.get(feeds_db_url, timeout=10)
        response.raise_for_status()
        feeds = response.json().get("rows", [])

        total = len(feeds)
        tasks: list[tuple[str, str, str, str | None, str | None]] = []
        skipped = 0

        for feed_item in feeds:
            doc = feed_item.get("doc")
            if doc and str(doc.get("_id", "")).startswith("_design/"):
                skipped += 1
                continue
            if doc and doc.get("_id") and doc.get("url"):
                original_url = doc.get("original_url") or doc.get("url")
                tasks.append(
                    (
                        doc["_id"],
                        doc["url"],
                        original_url,
                        doc.get("etag"),
                        doc.get("last_modified"),
                    )
                )
            elif doc:
                skipped += 1
                logger.warning(f"Scheduler: Skipping invalid feed document: {doc}")
                add_scheduler_log(
                    "feed_skipped",
                    "Skipping invalid feed document.",
                    {"id": doc.get("_id", "unknown")},
                )
            else:
                skipped += 1

        if tasks:
            workers = min(_max_workers(), len(tasks))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_run_feed_task, *task) for task in tasks]
                for future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Scheduler: Feed task failed: {e}")

        return {"total": total, "started": len(tasks), "skipped": skipped}

    except requests.exceptions.RequestException as e:
        logger.error(f"Scheduler: Error fetching feeds from CouchDB: {e}")
        add_scheduler_log(
            "feed_fetch_error",
            "Failed to fetch feeds from CouchDB.",
            {"error": str(e)},
        )
    except Exception as e:
        logger.error(f"Scheduler: An unexpected error occurred: {e}")
        add_scheduler_log(
            "scheduler_error",
            "Scheduler encountered an unexpected error.",
            {"error": str(e)},
        )

    return {"total": 0, "started": 0, "skipped": 0, "error": "fetch_failed"}


def scheduler_loop(initial_interval: int) -> None:
    db_url = get_couchdb_uri()
    feeds_db_url = f"{db_url}feeds/_all_docs?include_docs=true"
    was_paused = False

    while True:
        current_interval = get_dynamic_interval(initial_interval)

        if current_interval <= 0:
            if not was_paused:
                add_scheduler_log("paused", "Scheduler paused.")
            was_paused = True
            logger.info("Scheduler paused. Checking again in 60s.")
            time.sleep(60)
            continue

        if was_paused:
            add_scheduler_log(
                "resumed",
                "Scheduler resumed.",
                {"interval": str(current_interval)},
            )
            was_paused = False

        add_scheduler_log(
            "cycle_start",
            "Scheduler fetch cycle started.",
            {"interval": str(current_interval)},
        )
        result = _process_feeds(feeds_db_url)
        if result.get("error"):
            add_scheduler_log(
                "cycle_error",
                "Scheduler fetch cycle encountered errors.",
                {"error": str(result.get("error"))},
            )
        else:
            add_scheduler_log(
                "cycle_complete",
                "Scheduler fetch cycle completed.",
                {
                    "total": str(result.get("total", 0)),
                    "started": str(result.get("started", 0)),
                    "skipped": str(result.get("skipped", 0)),
                },
            )
        time.sleep(current_interval)


class SchedulerWrapper:
    def start(self, iteration_interval: int) -> None:
        try:
            interval = int(iteration_interval)
        except (TypeError, ValueError):
            interval = 600  # default interval in seconds
        logger.info(f"Scheduling tasks to run once every {interval} seconds.")

        # Start the scheduler loop in a daemon thread.
        scheduler_thread = threading.Thread(target=scheduler_loop, args=(interval,))
        scheduler_thread.daemon = True
        scheduler_thread.start()


# Expose a scheduler instance with a start method.
scheduler = SchedulerWrapper()
