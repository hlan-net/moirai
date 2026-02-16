# gunicorn.conf.py
# In gunicorn.conf.py
import multiprocessing
import logging
from main import start_services

logger = logging.getLogger("gunicorn.error")

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
    logger.info("Gunicorn starting, initializing background services...")
    start_services()  # Start the background tasks
