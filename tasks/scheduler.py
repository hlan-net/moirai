import os
import threading
import time
import requests
import logging
from api.db_config import get_couchdb_uri
from .fetch_feed_task import FetchFeedTask

logger = logging.getLogger(__name__)


def get_dynamic_interval(default_interval):
    db_url = get_couchdb_uri()
    try:
        res = requests.get(f"{db_url}config/main", timeout=2)
        if res.status_code == 200:
            config = res.json()
            return int(config.get("iteration_interval", default_interval))
    except Exception:
        pass
    return default_interval


def scheduler_loop(initial_interval):
    current_interval = initial_interval
    db_url = get_couchdb_uri()
    feeds_db_url = f"{db_url}feeds/_all_docs?include_docs=true"
    
    # Run tasks once per iteration interval.
    while True:
        # Check for dynamic interval update
        current_interval = get_dynamic_interval(initial_interval)

        if current_interval <= 0:
            logger.info(
                f"Scheduler paused (Interval: {current_interval}). Checking again in 60s."
            )
            time.sleep(60)
            continue

        logger.info(f"Scheduler: Starting fetch cycle (Interval: {current_interval}s)")

        try:
            # Credentials are now handled in get_couchdb_uri() via basic auth in URL
            response = requests.get(feeds_db_url, timeout=10)
            response.raise_for_status()
            feeds = response.json().get("rows", [])

            for feed_item in feeds:
                doc = feed_item.get("doc")
                if doc:
                    feed_id = doc.get("_id")
                    url = doc.get("url")
                    original_url = doc.get("original_url")
                    
                    if feed_id and url and original_url:
                        FetchFeedTask(feed_id, url, original_url).start()
                    else:
                        logger.warning(f"Scheduler: Skipping invalid feed document: {doc}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Scheduler: Error fetching feeds from CouchDB: {e}")
        except Exception as e:
            logger.error(f"Scheduler: An unexpected error occurred: {e}")


        time.sleep(current_interval)


class SchedulerWrapper:
    def start(self, iteration_interval):
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
