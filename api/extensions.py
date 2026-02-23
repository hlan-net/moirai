import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from prometheus_flask_exporter import PrometheusMetrics


def _get_rate_limit_storage_uri() -> str:
    """Build the storage URI for Flask-Limiter.

    Uses Redis when REDIS_HOST is set (recommended for multi-replica
    deployments), otherwise falls back to in-process memory.
    """
    redis_host = os.environ.get("REDIS_HOST")
    if redis_host:
        redis_port = os.environ.get("REDIS_PORT", "6379")
        redis_password = os.environ.get("REDIS_PASSWORD")
        if redis_password:
            return f"redis://:{redis_password}@{redis_host}:{redis_port}/0"
        return f"redis://{redis_host}:{redis_port}/0"
    return "memory://"


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    headers_enabled=True,
    storage_uri=_get_rate_limit_storage_uri(),
    strategy="fixed-window",
)

metrics = PrometheusMetrics(app=None)
