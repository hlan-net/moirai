"""Unit tests for the bounded scheduler feed-fetch pool and conditional HTTP fetches."""

import os
import threading
import time
from unittest.mock import MagicMock, patch

os.environ.setdefault("ADMIN_PASSWORD", "test_password")

from tasks.fetch_feed_task import FetchFeedTask  # noqa: E402
from tasks.scheduler import _max_workers, _process_feeds  # noqa: E402


def test_max_workers_env_parsing(monkeypatch):
    monkeypatch.delenv("SCHEDULER_MAX_WORKERS", raising=False)
    assert _max_workers() == 4

    monkeypatch.setenv("SCHEDULER_MAX_WORKERS", "6")
    assert _max_workers() == 6

    monkeypatch.setenv("SCHEDULER_MAX_WORKERS", "0")
    assert _max_workers() == 1

    monkeypatch.setenv("SCHEDULER_MAX_WORKERS", "not-an-int")
    assert _max_workers() == 4


def test_process_feeds_bounds_concurrency_and_skips_design_docs(monkeypatch):
    monkeypatch.setenv("SCHEDULER_MAX_WORKERS", "2")
    rows = [
        {"doc": {"_id": "_design/feeds"}},
        {"doc": {"_id": "invalid-without-url"}},
        *[
            {
                "doc": {
                    "_id": f"feed-{i}",
                    "url": f"https://example.com/{i}.xml",
                    "etag": f'"etag-{i}"',
                }
            }
            for i in range(6)
        ],
    ]
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"rows": rows}

    lock = threading.Lock()
    active = 0
    peak = 0
    seen_etags: list[str | None] = []

    def fake_fetch_url(self):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            seen_etags.append(self.etag)
        time.sleep(0.02)
        with lock:
            active -= 1

    with (
        patch("tasks.scheduler.requests.get", return_value=mock_resp),
        patch("tasks.scheduler.add_scheduler_log") as mock_log,
        patch.object(FetchFeedTask, "fetch_url", fake_fetch_url),
    ):
        result = _process_feeds("http://couchdb/feeds/_all_docs?include_docs=true")

    assert result == {"total": 8, "started": 6, "skipped": 2}
    assert peak <= 2
    assert sorted(seen_etags) == [f'"etag-{i}"' for i in range(6)]
    # Only the malformed non-design doc logs a feed_skipped warning
    mock_log.assert_called_once()


def test_fetch_feed_task_conditional_get_and_304():
    task = FetchFeedTask(
        "feed-1",
        "https://example.com/rss.xml",
        "https://example.com/rss.xml",
        etag='"v1"',
        last_modified="Mon, 26 Oct 2026 12:00:00 GMT",
    )
    resp_304 = MagicMock(status_code=304)

    with (
        patch("tasks.fetch_feed_task.requests.put") as mock_put,
        patch("tasks.fetch_feed_task.requests.get", return_value=resp_304) as mock_get,
        patch.object(task, "clear_fetch_error") as mock_clear,
        patch.object(task, "process_articles") as mock_parse,
    ):
        task.fetch_url()

    assert mock_put.call_count == 2
    headers = mock_get.call_args.kwargs["headers"]
    assert headers["If-None-Match"] == '"v1"'
    assert headers["If-Modified-Since"] == "Mon, 26 Oct 2026 12:00:00 GMT"
    mock_clear.assert_called_once()
    mock_parse.assert_not_called()
