"""Unit tests for scripts/reannotate_outdated.py."""

import os
import threading
import time

os.environ.setdefault("ADMIN_PASSWORD", "test_password")

from unittest.mock import patch

import pytest

from scripts.reannotate_outdated import (
    Progress,
    _view_ranges,
    count_outdated,
    iter_outdated,
    main,
    outdated_selector,
    reannotate,
    run,
)
from tasks.annotator import ANNOTATION_VERSION


def test_selector_targets_annotated_articles_behind_current_version():
    selector = outdated_selector(None)
    assert selector["annotations"] == {"$exists": True}
    assert {"annotation_version": {"$exists": False}} in selector["$or"]
    assert {"annotation_version": {"$lt": ANNOTATION_VERSION}} in selector["$or"]
    assert "userspace" not in selector


def test_selector_scopes_to_userspace():
    assert outdated_selector("abc")["userspace"] == "abc"


def test_selector_days_adds_published_cutoff():
    selector = outdated_selector(None, days=7)
    cutoff = selector["published"]["$gte"]
    assert len(cutoff) == len("2026-01-01T00:00:00")
    assert cutoff < "9999"
    assert "published" not in outdated_selector(None)


@patch("scripts.reannotate_outdated.requests.post")
def test_iter_outdated_pages_with_bookmark_until_empty(mock_post):
    pages = [
        {"docs": [{"_id": "a"}, {"_id": "b"}], "bookmark": "bm1"},
        {"docs": [{"_id": "c"}], "bookmark": "bm2"},
        {"docs": [], "bookmark": "bm3"},
    ]
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.side_effect = pages

    assert [d["_id"] for d in iter_outdated(None, limit=10)] == ["a", "b", "c"]
    assert mock_post.call_args_list[1].kwargs["json"]["bookmark"] == "bm1"


@patch("scripts.reannotate_outdated.requests.post")
def test_iter_outdated_respects_limit(mock_post):
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {
        "docs": [{"_id": "a"}, {"_id": "b"}],
        "bookmark": "bm",
    }
    assert len(list(iter_outdated(None, limit=2))) == 2
    assert mock_post.call_args.kwargs["json"]["limit"] == 2


@patch("scripts.reannotate_outdated.store_annotation")
@patch("scripts.reannotate_outdated.annotate_article")
def test_reannotate_passes_language_and_stores(mock_annotate, mock_store):
    mock_annotate.return_value = {
        "topics": ["culture"],
        "priority": "low",
        "sentiment": "neutral",
    }
    mock_store.return_value = True
    doc = {"_id": "x", "title": "T", "summary": "S", "language": "fi"}

    assert reannotate(doc, dry_run=False) is True
    mock_annotate.assert_called_once_with("T", "S", language="fi")
    mock_store.assert_called_once_with("x", mock_annotate.return_value)


@patch("scripts.reannotate_outdated.annotate_article")
def test_dry_run_does_not_call_model(mock_annotate):
    assert reannotate({"_id": "x", "title": "T"}, dry_run=True) is True
    mock_annotate.assert_not_called()


# --- count, progress and concurrency (#273) ---------------------------------


def test_view_ranges_cover_missing_and_older_versions():
    ranges = _view_ranges(None, None)
    versions = [r["start_key"][1] for r in ranges]
    assert versions == [None, *range(ANNOTATION_VERSION)]
    assert all(r["start_key"][0] == "*" for r in ranges)
    assert all(r["end_key"][2] == {} for r in ranges)


def test_view_ranges_scope_and_cutoff():
    ranges = _view_ranges("us-1", 7)
    assert all(r["start_key"][0] == "us-1" for r in ranges)
    assert all(len(r["start_key"]) == 3 for r in ranges)
    assert ranges[0]["start_key"][2] == outdated_selector(None, 7)["published"]["$gte"]


@patch("scripts.reannotate_outdated.requests.post")
def test_count_sums_reduce_results(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "results": [{"rows": [{"key": None, "value": 5}]}, {"rows": []}]
        + [{"rows": [{"key": None, "value": 2}]}] * (ANNOTATION_VERSION - 1)
    }
    assert count_outdated(None, 7) == 5 + 2 * (ANNOTATION_VERSION - 1)
    assert mock_post.call_args.args[0].endswith("/_view/by_version/queries")


@patch("scripts.reannotate_outdated.requests.post")
def test_count_falls_back_to_scan_without_view(mock_post):
    missing = type("R", (), {"status_code": 404})()
    page = type(
        "R",
        (),
        {
            "status_code": 200,
            "raise_for_status": lambda self: None,
            "json": lambda self: {"docs": [{"_id": "a"}, {"_id": "b"}]},
        },
    )()
    empty = type(
        "R",
        (),
        {
            "status_code": 200,
            "raise_for_status": lambda self: None,
            "json": lambda self: {"docs": []},
        },
    )()
    mock_post.side_effect = [missing, page, empty]
    assert count_outdated(None, None) == 2
    assert mock_post.call_args_list[1].kwargs["json"]["fields"] == ["_id"]


def test_progress_logs_at_interval_with_eta(caplog):
    progress = Progress(total=10, every=2)
    with caplog.at_level("INFO", logger="reannotate"):
        progress.record(True)
        assert not caplog.records
        progress.record(False)
    assert len(caplog.records) == 1
    msg = caplog.records[0].getMessage()
    assert "2/10 (20.0%)" in msg and "1 failed" in msg and "ETA" in msg


@pytest.mark.parametrize("concurrency", [1, 3])
@patch("scripts.reannotate_outdated.reannotate")
def test_run_counts_successes_and_failures(mock_reannotate, concurrency):
    mock_reannotate.side_effect = lambda doc, dry_run: doc["_id"] != "bad"
    docs = [{"_id": i} for i in ("a", "bad", "c", "d")]
    progress = Progress(total=4, every=0)

    assert run(docs, progress, concurrency=concurrency) is True
    assert (progress.done, progress.failed) == (3, 1)
    assert mock_reannotate.call_count == 4


@patch("scripts.reannotate_outdated.reannotate")
def test_run_exception_in_one_worker_does_not_stop_others(mock_reannotate):
    def flaky(doc, dry_run):
        if doc["_id"] == "boom":
            raise RuntimeError("backend exploded")
        return True

    mock_reannotate.side_effect = flaky
    progress = Progress(total=3, every=0)
    docs = [{"_id": "a"}, {"_id": "boom"}, {"_id": "c"}]
    assert run(docs, progress, concurrency=2) is True
    assert (progress.done, progress.failed) == (2, 1)


@patch("scripts.reannotate_outdated.reannotate")
def test_run_bounds_in_flight_work(mock_reannotate):
    lock = threading.Lock()
    state = {"now": 0, "peak": 0}

    def slow(doc, dry_run):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.02)
        with lock:
            state["now"] -= 1
        return True

    mock_reannotate.side_effect = slow
    progress = Progress(total=12, every=0)
    assert run(({"_id": i} for i in range(12)), progress, concurrency=3)
    assert progress.done == 12
    assert 1 < state["peak"] <= 3


@patch("scripts.reannotate_outdated.reannotate")
def test_run_interrupt_reports_stop(mock_reannotate):
    def docs():
        yield {"_id": "a"}
        raise KeyboardInterrupt

    mock_reannotate.return_value = True
    for concurrency in (1, 2):
        progress = Progress(total=2, every=0)
        assert run(docs(), progress, concurrency=concurrency) is False
        assert progress.done == 1


@patch("scripts.reannotate_outdated.iter_outdated")
@patch("scripts.reannotate_outdated.count_outdated", return_value=42)
def test_dry_run_only_counts(mock_count, mock_iter, caplog):
    with caplog.at_level("INFO", logger="reannotate"):
        assert main(["--dry-run"]) == 0
    mock_iter.assert_not_called()
    assert "42 article(s) behind version" in caplog.text


@patch("scripts.reannotate_outdated.reannotate", return_value=True)
@patch("scripts.reannotate_outdated.iter_outdated")
@patch("scripts.reannotate_outdated.count_outdated", side_effect=[3, 1])
def test_summary_reports_remaining(mock_count, mock_iter, mock_re, caplog):
    mock_iter.return_value = iter([{"_id": "a"}, {"_id": "b"}])
    with caplog.at_level("INFO", logger="reannotate"):
        assert main(["--limit", "2"]) == 0
    assert "2/2 (100.0%)" in caplog.text
    assert "1 article(s) still behind version" in caplog.text
    assert "re-run to continue" in caplog.text


def test_concurrency_must_be_positive():
    with pytest.raises(SystemExit):
        main(["--concurrency", "0"])
