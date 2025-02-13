import os
import threading
import time
from .fetch_feed_task import FetchFeedTask
from .event_correlator import EventCorrelator

def scheduler_loop(interval):
    # Run tasks once per iteration interval.
    while True:
        # Assuming FetchFeedTask and EventCorrelator are callable as tasks.
        EventCorrelator().run()
        # Collect list of feeds in the files in feeds directory and setup Task for each feed to fecth them.
        feeds_directory = 'feeds'
        for filename in os.listdir(feeds_directory):
            filepath = os.path.join(feeds_directory, filename)
            if os.path.isfile(filepath):
                with open(filepath, 'r') as file:
                    for line in file.readlines():
                        url = line.strip()
                        if url:
                            # Assuming a delay of 0 for simplicity.  Adjust as needed.
                            FetchFeedTask(url, 0).start()
        time.sleep(interval)

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