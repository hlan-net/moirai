import os
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Deque

import bleach

_LOG_LIMIT = int(os.environ.get("SCHEDULER_LOG_LIMIT", "100"))
_LOG_LOCK = threading.Lock()
_LOGS: Deque[dict[str, object]] = deque(maxlen=_LOG_LIMIT)


def _sanitize_text(value: str) -> str:
    return bleach.clean(value)


def add_scheduler_log(
    event: str,
    message: str,
    metadata: dict[str, object] | None = None,
) -> None:
    entry: dict[str, object] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": _sanitize_text(event),
        "message": _sanitize_text(message),
    }

    if metadata:
        entry["metadata"] = {key: _sanitize_text(str(value)) for key, value in metadata.items()}

    with _LOG_LOCK:
        _LOGS.append(entry)


def get_scheduler_logs() -> list[dict[str, object]]:
    with _LOG_LOCK:
        return list(_LOGS)
