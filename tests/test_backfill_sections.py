"""Tests for scripts/backfill_sections.py — conflict retry and failure reporting."""

from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch

import pytest

from scripts import backfill_sections as bf

URI = "http://couch/"


def _resp(payload: object) -> MagicMock:
    res = MagicMock()
    res.json.return_value = payload
    res.raise_for_status.return_value = None
    return res


def _article(doc_id: str, rev: str = "1-a", **extra: object) -> dict:
    return {
        "_id": doc_id,
        "_rev": rev,
        "link": "https://example.com/news/x",
        "feed_url": "https://example.com/rss",
        **extra,
    }


@pytest.fixture(autouse=True)
def _couch_uri():
    with (
        patch.object(bf, "get_couchdb_uri", return_value=URI),
        patch.object(bf, "_invalidate_stream_cache"),
    ):
        yield


class _FakeCouch:
    """Minimal stand-in for the three CouchDB endpoints the backfill uses."""

    def __init__(self, articles: list[dict], bulk_results: list[list[dict]]):
        self.articles = {a["_id"]: a for a in articles}
        self.bulk_results = list(bulk_results)
        self.bulk_calls: list[list[dict]] = []
        self.fetch_calls: list[list[str]] = []

    def get(self, url: str, params: dict | None = None, timeout: int = 0):
        if url.endswith("feeds/_all_docs"):
            return _resp({"rows": []})
        rows = [
            {"id": i, "doc": copy.deepcopy(d)} for i, d in sorted(self.articles.items())
        ]
        return _resp({"rows": rows})

    def post(self, url: str, json: dict, params: dict | None = None, timeout: int = 0):
        if url.endswith("_bulk_docs"):
            self.bulk_calls.append([dict(d) for d in json["docs"]])
            return _resp(self.bulk_results.pop(0))
        self.fetch_calls.append(list(json["keys"]))
        return _resp(
            {
                "rows": [
                    (
                        {"id": k, "doc": copy.deepcopy(self.articles[k])}
                        if k in self.articles
                        else {"key": k, "error": "not_found"}
                    )
                    for k in json["keys"]
                ]
            }
        )


def _run(couch: _FakeCouch, argv: list[str] | None = None) -> int:
    with (
        patch.object(bf.requests, "get", side_effect=couch.get),
        patch.object(bf.requests, "post", side_effect=couch.post),
    ):
        return bf.main(argv or [])


def test_all_written_exits_zero():
    couch = _FakeCouch(
        [_article("a"), _article("b")],
        [[{"id": "a", "ok": True}, {"id": "b", "ok": True}]],
    )
    assert _run(couch) == 0
    assert len(couch.bulk_calls) == 1
    assert all(d["section"] for d in couch.bulk_calls[0])


def test_conflict_is_refetched_and_retried():
    couch = _FakeCouch(
        [_article("a"), _article("b")],
        [
            [{"id": "a", "ok": True}, {"id": "b", "error": "conflict"}],
            [{"id": "b", "ok": True}],
        ],
    )
    # The concurrent writer bumped b's revision.
    couch.articles["b"] = _article("b", rev="2-b")
    assert _run(couch) == 0
    assert couch.fetch_calls == [["b"]]
    retried = couch.bulk_calls[1]
    assert [d["_id"] for d in retried] == ["b"]
    assert retried[0]["_rev"] == "2-b"
    assert retried[0]["section"]


def test_conflict_already_sectioned_by_other_writer_is_not_rewritten():
    couch = _FakeCouch(
        [_article("a")],
        [[{"id": "a", "error": "conflict"}]],
    )
    original_get = couch.get
    first_page_served = False

    def get(url: str, params: dict | None = None, timeout: int = 0):
        nonlocal first_page_served
        res = original_get(url, params, timeout)
        if url.endswith("articles/_all_docs") and not first_page_served:
            first_page_served = True
            # After the page is read, the annotation worker sections it.
            couch.articles["a"] = _article(
                "a", rev="2-a", section="sports", section_source="topic"
            )
        return res

    couch.get = get  # type: ignore[method-assign]
    assert _run(couch) == 0
    assert len(couch.bulk_calls) == 1  # no retry write needed


def test_persistent_conflict_fails_the_run():
    couch = _FakeCouch(
        [_article("a")],
        [[{"id": "a", "error": "conflict"}]] * (bf.MAX_CONFLICT_RETRIES + 1),
    )
    assert _run(couch) == 1
    assert len(couch.bulk_calls) == bf.MAX_CONFLICT_RETRIES + 1


def test_hard_rejection_fails_the_run():
    couch = _FakeCouch(
        [_article("a")],
        [[{"id": "a", "error": "forbidden", "reason": "validation"}]],
    )
    assert _run(couch) == 1
    assert len(couch.bulk_calls) == 1


def test_dry_run_writes_nothing():
    couch = _FakeCouch([_article("a")], [])
    assert _run(couch, ["--dry-run"]) == 0
    assert couch.bulk_calls == []
