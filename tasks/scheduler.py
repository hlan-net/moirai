import os
import threading
import time
import requests
import json
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
    # Run tasks once per iteration interval.
    while True:
        # Check for dynamic interval update
        current_interval = get_dynamic_interval(initial_interval)
        
        if current_interval <= 0:
            print(f"Scheduler paused (Interval: {current_interval}). Checking again in 60s.")
            time.sleep(60)
            continue

        print(f"Scheduler: Starting fetch cycle (Interval: {current_interval}s)")
        
        # First, fetch new feeds
        feeds_directory = './feeds'
        # Create the feeds directory if it doesn't exist
        if not os.path.exists(feeds_directory):
            os.makedirs(feeds_directory)
        for filename in os.listdir(feeds_directory):
            filepath = os.path.join(feeds_directory, filename)
            if os.path.isfile(filepath):
                with open(filepath, 'r') as file:
                    for line in file.readlines():
                        url = line.strip()
                        if url:
                            # Assuming a delay of 0 for simplicity. Adjust as needed.
                            FetchFeedTask(url, 0).start()
        
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