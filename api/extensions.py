import os
import hashlib
import redis
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request
from prometheus_flask_exporter import PrometheusMetrics
from tasks.session_logger import SessionLogger


def get_redis_client() -> redis.Redis:
    """Return a shared Redis client instance (or None if not configured)."""
    host = os.environ.get("REDIS_HOST")
    if not host:
        return None
    
    port = int(os.environ.get("REDIS_PORT", 6379))
    password = os.environ.get("REDIS_PASSWORD")
    
    return redis.Redis(
        host=host,
        port=port,
        password=password,
        db=0,
        decode_responses=True,  # Return strings instead of bytes
    )


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


def _rate_limit_key() -> str:
    """Build a stable limiter key with auth-aware fallbacks.

    Priority:
    1) Bearer token hash (distinguishes users behind shared proxies)
    2) X-Forwarded-For first hop
    3) X-Real-IP
    4) Remote address fallback
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            return f"token:{token_hash[:16]}"

    x_forwarded_for = request.headers.get("X-Forwarded-For", "")
    if x_forwarded_for:
        forwarded_ip = x_forwarded_for.split(",")[0].strip()
        if forwarded_ip:
            return f"ip:{forwarded_ip}"

    x_real_ip = request.headers.get("X-Real-IP", "").strip()
    if x_real_ip:
        return f"ip:{x_real_ip}"

    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["200 per day", "50 per hour"],
    headers_enabled=True,
    storage_uri=_get_rate_limit_storage_uri(),
    strategy="fixed-window",
)

metrics = PrometheusMetrics(app=None)


def get_session_logger() -> SessionLogger:
    """Return a SessionLogger backed by the configured Redis client (or a no-op one)."""
    return SessionLogger(get_redis_client())
