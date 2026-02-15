import os
import threading
import time
import requests
from urllib.parse import quote
from .fetch_feed_task import FetchFeedTask


def get_dynamic_interval(default_interval):
    uri = os.environ.get("COUCHDB_URI", "http://localhost:5984/").rstrip("/")
    user = os.environ.get("COUCHDB_USER")
    password = os.environ.get("COUCHDB_PASSWORD")
    if user and password and "@" not in uri:
        if "://" in uri:
            scheme, host = uri.split("://", 1)
        else:
            scheme, host = "http", uri
        uri = f"{scheme}://{quote(user)}:{quote(password)}@{host}"

    db_url = uri + "/"
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
    db_url = os.environ.get("COUCHDB_URI", "http://localhost:5984/").rstrip("/")
    feeds_db_url = f"{db_url}/feeds/_all_docs?include_docs=true"
    
    # Run tasks once per iteration interval.
    while True:
        # Check for dynamic interval update
        current_interval = get_dynamic_interval(initial_interval)

        if current_interval <= 0:
            print(
                f"Scheduler paused (Interval: {current_interval}). Checking again in 60s."
            )
            time.sleep(60)
            continue

        print(f"Scheduler: Starting fetch cycle (Interval: {current_interval}s)")

        try:
            auth = (os.environ.get("COUCHDB_USER"), os.environ.get("COUCHDB_PASSWORD"))
            response = requests.get(feeds_db_url, auth=auth, timeout=10)
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
                        print(f"Scheduler: Skipping invalid feed document: {doc}")

        except requests.exceptions.RequestException as e:
            print(f"Scheduler: Error fetching feeds from CouchDB: {e}")
        except Exception as e:
            print(f"Scheduler: An unexpected error occurred: {e}")


        time.sleep(current_interval)


class SchedulerWrapper:
    def start(self, iteration_interval):
        try:
            interval = int(iteration_interval)
        except (TypeError, ValueError):
            interval = 600  # default interval in seconds
        print(f"Scheduling tasks to run once every {interval} seconds.")

        # Start the scheduler loop in a daemon thread.
        scheduler_thread = threading.Thread(target=scheduler_loop, args=(interval,))
        scheduler_thread.daemon = True
        scheduler_thread.start()


# Expose a scheduler instance with a start method.
scheduler = SchedulerWrapper()
