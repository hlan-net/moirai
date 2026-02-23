import os

# Server socket
host = os.environ.get("HTTP_HOST", "0.0.0.0")
bind = f"{host}:8088"
pidfile = "/run/gunicorn/gunicorn.pid"

# Worker processes
# In Kubernetes, scale horizontally via pod replicas rather than spawning
# many workers inside a single pod.  WEB_CONCURRENCY env var can override.
workers = int(os.environ.get("WEB_CONCURRENCY", 1))
worker_class = "sync"
worker_tmp_dir = "/dev/shm"

# Logging
accesslog = "-"
errorlog = "-"


def on_starting(server):
    """Initialise databases and default user on gunicorn startup.

    Note: The scheduler and enrichment worker are started separately
    (via run_worker.py / the worker Docker service) and are intentionally
    NOT started here to keep the API process decoupled.
    """
    if os.environ.get("ENABLE_PROD_STARTUP", "false").lower() == "true":
        import init_db

        init_db.run()
