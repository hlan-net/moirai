# gunicorn.conf.py
# In gunicorn.conf.py
import multiprocessing
from main import start_services

# Server socket
bind = "0.0.0.0:8088"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"

# Logging
accesslog = "-"
errorlog = "-"

# Server hooks
def on_starting(server):
    """
    Server hook that is called just before the master process is forked.
    """
    print("Gunicorn starting, initializing background services...")
    start_services()  # Start the background tasks
