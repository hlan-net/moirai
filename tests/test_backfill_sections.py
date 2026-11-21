"""Tests for scripts/backfill_sections.py — conflict retry and failure reporting."""

from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch

import pytest

from scripts import backfill_sections as bf

URI = "http://couch/"

# The real helpers; the autouse fixture below replaces them on the module.
_REAL_READ_MARKER = bf._read_marker
_REAL_WRITE_MARKER = bf._write_marker


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
        # No completion marker on record unless a test says otherwise.
        patch.object(bf, "_read_marker", return_value=None),
        patch.object(bf, "_write_marker"),
    ):
        yield


class _FakeCouch:
    """Minimal stand-in for the three CouchDB endpoints the backfill uses."""

    def __init__(
        self,
        articles: list[dict],
        bulk_results: list[list[dict]],
        feeds: list[dict] | None = None,
    ):
        self.articles = {a["_id"]: a for a in articles}
        self.feeds = feeds or []
        self.bulk_results = list(bulk_results)
        self.bulk_calls: list[list[dict]] = []
        self.fetch_calls: list[list[str]] = []

    def get(self, url: str, params: dict | None = None, timeout: int = 0):
        if url.endswith("feeds/_all_docs"):
            return _resp({"rows": [{"id": f["_id"], "doc": f} for f in self.feeds]})
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
                "a",
                rev="2-a",
                section="sports",
                section_source="topic",
                annotations={"topics": ["sports"]},
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
        [[{"id": "a", "error": "unauthorized", "reason": "no write access"}]],
    )
    assert _run(couch) == 1
    assert len(couch.bulk_calls) == 1


def test_dry_run_writes_nothing():
    couch = _FakeCouch([_article("a")], [])
    assert _run(couch, ["--dry-run"]) == 0
    assert couch.bulk_calls == []


def test_invalid_stored_article_is_skipped_not_failed():
    # A legacy article that fails validate_doc_update can never be written;
    # failing the run for it would fail every rerun too.
    couch = _FakeCouch(
        [_article("a"), _article("b")],
        [
            [
                {"id": "a", "ok": True},
                {"id": "b", "error": "forbidden", "reason": "published must be ISO"},
            ]
        ],
    )
    assert _run(couch) == 0
    assert len(couch.bulk_calls) == 1


def test_default_mode_keeps_feed_decisions():
    couch = _FakeCouch(
        [_article("a", section="culture", section_source="feed")],
        [],
    )
    assert _run(couch) == 0
    assert couch.bulk_calls == []


def test_default_mode_refiles_weaker_decision_when_feed_has_category():
    # Sectioned by the annotator (topic) before the backfill could apply the
    # feed's category: the default mode must still pick the feed decision.
    couch = _FakeCouch(
        [
            _article(
                "a",
                section="main",
                section_source="default",
                annotations={"topics": ["politics"]},
            )
        ],
        [[{"id": "a", "ok": True}]],
        feeds=[{"_id": "f1", "url": "https://example.com/rss", "category": "sports"}],
    )
    assert _run(couch) == 0
    written = couch.bulk_calls[0][0]
    assert (written["section"], written["section_source"]) == ("sports", "feed")


def test_default_mode_writes_nothing_when_up_to_date():
    couch = _FakeCouch(
        [
            _article(
                "a",
                section="main",
                section_source="default",
            )
        ],
        [],
    )
    assert _run(couch) == 0
    assert couch.bulk_calls == []


def test_start_background_runs_the_startup_run():
    with patch.object(bf, "run", return_value={"failed": 0}) as run:
        bf.start_background().join(timeout=5)
    run.assert_called_once_with(recompute_all=False, dry_run=False)


def test_start_background_swallows_errors(_no_retry_delay):
    with patch.object(bf, "run", side_effect=RuntimeError("couch down")):
        thread = bf.start_background()
        thread.join(timeout=5)
    assert not thread.is_alive()


@pytest.fixture
def _no_retry_delay():
    with (
        patch.object(bf, "RETRY_DELAYS_S", (1, 1, 1)),
        patch.object(bf.time, "sleep") as sleep,
    ):
        yield sleep


def test_background_run_retries_after_an_error(_no_retry_delay):
    outcomes = [RuntimeError("504 on page 40"), {"failed": 0}]

    def attempt():
        result = outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    bf._run_with_retry("test", attempt)
    assert outcomes == []
    assert _no_retry_delay.call_count == 1


def test_background_run_retries_unwritten_articles(_no_retry_delay):
    attempt = MagicMock(side_effect=[{"failed": 2}, {"failed": 0}])
    bf._run_with_retry("test", attempt)
    assert attempt.call_count == 2


def test_background_run_gives_up_without_raising(_no_retry_delay):
    attempt = MagicMock(side_effect=RuntimeError("couch down"))
    bf._run_with_retry("test", attempt)
    assert attempt.call_count == 1 + len(bf.RETRY_DELAYS_S)


def test_feed_refile_recomputes_feed_decided_articles_of_that_feed():
    # The feed moved from sports back to general: its feed-decided articles
    # must leave Sports, which the default mode would never do.
    feed_url = "https://example.com/rss"
    article = _article(
        "a",
        section="sports",
        section_source="feed",
        link="https://example.com/news/x",
    )
    finds: list[dict] = []
    bulk: list[list[dict]] = []

    def post(url: str, json: dict, params: dict | None = None, timeout: int = 0):
        if url.endswith("articles/_find"):
            finds.append(json)
            docs = (
                [copy.deepcopy(article)]
                if json["selector"]["feed_url"] == feed_url
                else []
            )
            return _resp({"docs": docs, "bookmark": "b1"})
        bulk.append(json["docs"])
        return _resp([{"id": d["_id"], "ok": True} for d in json["docs"]])

    feeds = {"rows": [{"id": "f1", "doc": {"url": feed_url, "category": "general"}}]}
    with (
        patch.object(bf.requests, "get", return_value=_resp(feeds)),
        patch.object(bf.requests, "post", side_effect=post),
    ):
        bf.start_feed_refile([feed_url, None, "https://old.example.com/rss"]).join(5)

    assert [f["selector"]["feed_url"] for f in finds] == [
        feed_url,
        "https://old.example.com/rss",
    ]
    assert len(bulk) == 1
    assert (bulk[0][0]["section"], bulk[0][0]["section_source"]) == ("main", "default")


def test_feed_article_pages_follow_the_bookmark():
    pages = [
        {"docs": [{"_id": "a"}, {"_id": "b"}], "bookmark": "b1"},
        {"docs": [{"_id": "c"}], "bookmark": "b2"},
    ]
    bodies: list[dict] = []

    def post(url: str, json: dict, timeout: int = 0):
        bodies.append(dict(json))
        return _resp(pages.pop(0))

    with patch.object(bf.requests, "post", side_effect=post):
        got = list(bf._iter_feed_article_pages(["https://x/rss"], page_size=2))

    assert [[d["_id"] for d in page] for page in got] == [["a", "b"], ["c"]]
    assert "bookmark" not in bodies[0]
    assert bodies[1]["bookmark"] == "b1"


def test_written_articles_are_marked_as_refiled():
    """The rewrite must not look like a new article in ``articles/_changes``."""
    couch = _FakeCouch(
        [_article("a1", rev="3-x")], [[{"ok": True, "id": "a1", "rev": "4-y"}]]
    )
    assert _run(couch) == 0
    assert couch.bulk_calls[0][0]["section_rewrite_gen"] == 4


def test_conflict_retry_marks_the_fresh_revision():
    couch = _FakeCouch(
        [_article("a1", rev="1-a")],
        [
            [{"id": "a1", "error": "conflict", "reason": "x"}],
            [{"ok": True, "id": "a1", "rev": "3-c"}],
        ],
    )

    def post(url: str, json: dict, params: dict | None = None, timeout: int = 0):
        if not url.endswith("_bulk_docs"):
            couch.articles["a1"]["_rev"] = "2-b"  # the concurrent writer's revision
        return couch.post(url, json, params=params, timeout=timeout)

    with (
        patch.object(bf.requests, "get", side_effect=couch.get),
        patch.object(bf.requests, "post", side_effect=post),
    ):
        assert bf.main([]) == 0
    assert couch.bulk_calls[1][0]["_rev"] == "2-b"
    assert couch.bulk_calls[1][0]["section_rewrite_gen"] == 3


# ── Startup run: a full scan only when one is owed (#324) ─────────────────────


def test_startup_scans_everything_and_records_completion_the_first_time():
    with patch.object(bf, "run", return_value={"failed": 0}) as run:
        bf.run_startup()
    run.assert_called_once_with(recompute_all=False, dry_run=False)
    bf._write_marker.assert_called_once_with()


def test_startup_does_not_record_completion_when_articles_were_left_unwritten():
    with patch.object(bf, "run", return_value={"failed": 3}):
        bf.run_startup()
    bf._write_marker.assert_not_called()


def test_startup_with_a_current_marker_reads_only_unsectioned_articles():
    """No ``_all_docs`` walk of ``articles`` once a complete scan is on record."""
    from tasks.sections import SECTION_RULES_VERSION

    bf._read_marker.return_value = SECTION_RULES_VERSION
    urls: list[str] = []

    def get(url: str, params: dict | None = None, timeout: int = 0):
        urls.append(url)
        return _resp({"rows": []})  # feeds/_all_docs

    def post(url: str, json: dict, params: dict | None = None, timeout: int = 0):
        urls.append(url)
        assert json["selector"] == {"section": {"$exists": False}}
        return _resp({"docs": []})

    with (
        patch.object(bf.requests, "get", side_effect=get),
        patch.object(bf.requests, "post", side_effect=post),
    ):
        summary = bf.run_startup()

    assert urls == [f"{URI}feeds/_all_docs", f"{URI}articles/_find"]
    assert summary["seen"] == 0 and summary["written"] == 0
    bf._write_marker.assert_not_called()


def test_startup_with_a_current_marker_still_files_an_unsectioned_article():
    from tasks.sections import SECTION_RULES_VERSION

    bf._read_marker.return_value = SECTION_RULES_VERSION
    stray = _article("a9", rev="1-a", link="https://www.hs.fi/urheilu/art-9.html")
    written: list[dict] = []

    def post(url: str, json: dict, params: dict | None = None, timeout: int = 0):
        if url.endswith("_find"):
            return _resp({"docs": [copy.deepcopy(stray)]})
        written.extend(json["docs"])
        return _resp([{"ok": True, "id": "a9", "rev": "2-b"}])

    with (
        patch.object(bf.requests, "get", return_value=_resp({"rows": []})),
        patch.object(bf.requests, "post", side_effect=post),
    ):
        summary = bf.run_startup()

    assert summary["written"] == 1
    assert written[0]["section"] == "sports"
    assert written[0]["section_source"] == "path"


def test_startup_rescans_everything_after_the_rules_version_changes():
    from tasks.sections import SECTION_RULES_VERSION

    bf._read_marker.return_value = SECTION_RULES_VERSION - 1
    with patch.object(bf, "run", return_value={"failed": 0}) as run:
        bf.run_startup()
    run.assert_called_once_with(recompute_all=False, dry_run=False)
    bf._write_marker.assert_called_once_with()


def test_manual_run_records_completion_but_a_dry_run_does_not():
    couch = _FakeCouch([_article("a1")], [[{"ok": True, "id": "a1", "rev": "2-b"}]])
    assert _run(couch) == 0
    bf._write_marker.assert_called_once_with()

    bf._write_marker.reset_mock()
    assert _run(_FakeCouch([_article("a1")], []), ["--dry-run"]) == 0
    bf._write_marker.assert_not_called()


def test_marker_round_trip():
    """The real marker helpers: read what write stored, tolerate a missing doc."""
    from tasks.sections import SECTION_RULES_VERSION

    store: dict[str, dict] = {}

    def get(url: str, timeout: int = 0):
        res = MagicMock()
        doc = store.get(url)
        res.status_code = 200 if doc else 404
        res.json.return_value = doc or {"error": "not_found"}
        return res

    def put(url: str, json: dict, timeout: int = 0):
        store[url] = {**json, "_rev": "1-x"}
        return MagicMock(status_code=201)

    with (
        patch.object(bf.requests, "get", side_effect=get),
        patch.object(bf.requests, "put", side_effect=put),
    ):
        assert _REAL_READ_MARKER() is None  # nothing stored yet
        _REAL_WRITE_MARKER()
        assert _REAL_READ_MARKER() == SECTION_RULES_VERSION
        _REAL_WRITE_MARKER()  # a second write carries the stored _rev

    (doc,) = store.values()
    assert doc["_id"] == "section_backfill"
    assert doc["completed_at"].endswith("Z")
