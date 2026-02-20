import os
import multiprocessing

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
