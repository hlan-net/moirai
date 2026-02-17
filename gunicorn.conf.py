import os
import multiprocessing
import logging
from main import start_services

logger = logging.getLogger("gunicorn.error")

# Server socket
host = os.environ.get("HTTP_HOST", "0.0.0.0")
bind = f"{host}:8088"
pidfile = "/run/gunicorn/gunicorn.pid"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_tmp_dir = "/dev/shm"

# Logging
accesslog = "-"
errorlog = "-"

# Server hooks
def on_starting(_server):
    """
    Server hook that is called just before the master process is forked.
    """
    logger.info("Gunicorn starting, initializing background services...")
    start_services()  # Start the background tasks
