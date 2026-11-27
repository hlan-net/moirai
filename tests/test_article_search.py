"""``GET /api/articles/search`` (#377): the Stream page's search.

The route answers with the items of ``/api/stream.rss`` when asked for
``format=rss``, so the page shows the results as its own rows.
"""

import os
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

os.environ.setdefault(
    "JWT_SECRET_KEY", "super_secret_test_key_that_is_at_least_32_chars_long"
)
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password_123")

import pytest  # noqa: E402
import requests  # noqa: E402

from api import db  # noqa: E402
from main import app  # noqa: E402

ARTICLE = {
    "_id": "a1",
    "title": "Derby Result",
    "link": "https://example.com/derby",
    "summary": "The derby ended in a draw." + " x" * 200,
    "published": "2024-01-01T10:00:00+00:00",
    "feed_url": "https://example.com/rss",
    "section": "sports",
}


@pytest.fixture
def search():
    """A logged-in client and the mocked article query.

    The search is two requests (#387): the ids of the matches from the search
    index (`query`), then those documents (`api.routes.fetch_docs_by_ids`).
    """
    hit = {"_id": ARTICLE["_id"], "published": ARTICLE["published"]}
    with (
        patch("api.auth.verify_request_auth", return_value=(True, "")),
        patch("api.routes.query_couchdb", return_value=[hit]) as query,
        patch("api.routes.fetch_docs_by_ids", return_value=[dict(ARTICLE)]),
        patch(
            "api.routes.fetch_from_couchdb",
            return_value=[{"url": "https://example.com/rss", "title": "Example"}],
        ),
        patch("api.routes.enrich_articles_with_issues") as enrich,
    ):
        yield app.test_client(), query, enrich


def test_search_needs_a_login():
    with patch("api.routes.query_couchdb") as query:
        res = app.test_client().get("/api/articles/search?q=derby")

    assert res.status_code == 401
    query.assert_not_called()


def test_search_matches_title_summary_and_content_newest_first(search):
    client, query, _ = search
    res = client.get("/api/articles/search?q=derby")

    assert res.status_code == 200
    kwargs = query.call_args.kwargs
    assert kwargs["sort"] == [{"published": "desc"}]
    assert kwargs["limit"] == 50
    selector = kwargs["selector"]
    # `published` is in the selector so that the sort can use its index.
    assert selector["published"] == {"$gt": None}
    assert selector["$or"] == [
        {"title": {"$regex": "(?i)derby"}},
        {"summary": {"$regex": "(?i)derby"}},
        {"content": {"$regex": "(?i)derby"}},
    ]


def test_search_is_answered_from_the_index_then_fetches_the_matches(search):
    """No document is loaded to test it: ids from the index, then those documents."""
    client, query, _ = search
    query.return_value = [
        {"_id": "a2", "published": "2024-01-02T10:00:00+00:00"},
        {"_id": "a1", "published": "2024-01-01T10:00:00+00:00"},
    ]
    with patch("api.routes.fetch_docs_by_ids", return_value=[dict(ARTICLE)]) as fetch:
        res = client.get("/api/articles/search?q=derby")

    assert res.status_code == 200
    kwargs = query.call_args.kwargs
    assert kwargs["use_index"] == "idx_search_text"
    # Only fields the index holds may be asked for, or documents are loaded.
    assert kwargs["fields"] == ["_id", "published"]
    selector = kwargs["selector"]
    # Every indexed field is named, or CouchDB will not choose the index.
    for field in ("title", "summary", "content"):
        assert selector[field] == {"$gt": None}
    assert set(selector) == {"published", "title", "summary", "content", "$or"}
    # Newest first, as the index returned them.
    fetch.assert_called_once_with("articles", ["a2", "a1"], raise_on_error=True)


def test_a_slow_search_is_not_repeated(search):
    """A timeout means the scan is slow; a retry would start a second one."""
    client, query, _ = search
    client.get("/api/articles/search?q=derby")

    kwargs = query.call_args.kwargs
    assert kwargs["retry"] is False
    assert kwargs["timeout"] == 20


def test_search_fails_when_the_matches_cannot_be_fetched(search):
    client, _, _ = search
    with patch(
        "api.routes.fetch_docs_by_ids",
        side_effect=requests.exceptions.ConnectionError("down"),
    ):
        res = client.get("/api/articles/search?q=derby")

    assert res.status_code == 503


def test_search_text_is_matched_literally(search):
    client, query, _ = search
    client.get("/api/articles/search", query_string={"q": "a.b (c)"})

    pattern = query.call_args.kwargs["selector"]["$or"][0]["title"]["$regex"]
    assert pattern == r"(?i)a\.b\ \(c\)"


def test_search_json_is_a_summary_of_each_article(search):
    client, _, enrich = search
    body = client.get("/api/articles/search?q=derby").get_json()

    assert body["total"] == 1
    assert body["query"] == "derby"
    result = body["results"][0]
    assert result["title"] == "Derby Result"
    assert result["description"] == ARTICLE["summary"][:200]
    enrich.assert_not_called()


def test_search_rss_carries_the_items_of_the_stream(search):
    client, _, enrich = search
    res = client.get("/api/articles/search?q=derby+%26+co&format=rss&limit=200")

    assert res.status_code == 200
    assert res.mimetype == "application/rss+xml"
    root = ET.fromstring(res.get_data(as_text=True))  # raises if malformed
    channel = root.find("channel")
    assert channel.find("title").text == "Moirai Search — derby & co"
    item = channel.find("item")
    assert item.find("title").text == "Derby Result"
    assert item.find("link").text == "https://example.com/derby"
    assert item.find("source").find("title").text == "Example"
    sections = [
        c.text for c in item.findall("category") if c.get("domain") == "section"
    ]
    assert sections == ["sports"]
    enrich.assert_called_once()


def test_search_dates_narrow_the_published_range(search):
    client, query, _ = search
    client.get("/api/articles/search?q=derby&from=2024-01-01&to=2024-01-31T12:00:00")

    assert query.call_args.kwargs["selector"]["published"] == {
        "$gte": "2024-01-01T00:00:00",
        "$lte": "2024-01-31T12:00:00",
    }


def test_search_with_only_an_end_date_keeps_the_index_bound(search):
    client, query, _ = search
    client.get("/api/articles/search?q=derby&to=2024-01-31")

    assert query.call_args.kwargs["selector"]["published"] == {
        "$gt": None,
        "$lte": "2024-01-31T00:00:00",
    }


@pytest.mark.parametrize("limit,expected", [("500", 200), ("0", 1), ("20", 20)])
def test_search_limit_is_clamped(search, limit, expected):
    client, query, _ = search
    client.get(f"/api/articles/search?q=derby&limit={limit}")

    assert query.call_args.kwargs["limit"] == expected


@pytest.mark.parametrize(
    "query_string",
    ["", "q=", "q=%20", "q=derby&limit=many", "q=derby&format=xml", "q=derby&from=x"],
)
def test_search_rejects_bad_parameters(search, query_string):
    client, query, _ = search
    res = client.get(f"/api/articles/search?{query_string}")

    assert res.status_code == 400
    query.assert_not_called()


@pytest.mark.parametrize("result_format", ["json", "rss"])
def test_search_failure_is_not_an_empty_result(search, result_format):
    """A CouchDB error or timeout must not read as "nothing mentions this"."""
    client, query, _ = search
    query.side_effect = requests.exceptions.Timeout("read timed out")

    res = client.get(f"/api/articles/search?q=derby&format={result_format}")

    assert res.status_code == 503
    assert query.call_args.kwargs["raise_on_error"] is True


# --- The CouchDB helpers the search uses (api/db.py) -------------------------


def _couch_response(payload: dict) -> MagicMock:
    res = MagicMock()
    res.status_code = 200
    res.json.return_value = payload
    return res


def test_query_names_the_index_and_the_timeout():
    session = MagicMock()
    session.request.return_value = _couch_response({"docs": [{"_id": "a1"}]})
    with patch("api.db.couchdb_session", return_value=session):
        docs = db.query_couchdb(
            "articles", {"published": {"$gt": None}}, use_index="idx", timeout=20
        )

    assert docs == [{"_id": "a1"}]
    kwargs = session.request.call_args.kwargs
    assert kwargs["json"]["use_index"] == "idx"
    assert kwargs["timeout"] == 20


@pytest.mark.parametrize("retry,attempts", [(False, 1), (True, 3)])
def test_query_without_retry_makes_one_attempt(retry, attempts):
    session = MagicMock()
    session.request.side_effect = requests.exceptions.Timeout("read timed out")
    with (
        patch("api.db.couchdb_session", return_value=session),
        patch("tenacity.nap.time.sleep"),
        pytest.raises(requests.exceptions.Timeout),
    ):
        db.query_couchdb("articles", {}, retry=retry, raise_on_error=True)

    assert session.request.call_count == attempts


def test_fetch_by_ids_keeps_the_order_and_skips_what_is_gone():
    session = MagicMock()
    session.request.return_value = _couch_response(
        {
            "rows": [
                {"id": "a2", "doc": {"_id": "a2"}},
                {"key": "gone", "error": "not_found"},
                {"id": "dead", "value": {"deleted": True}, "doc": None},
                {"id": "a1", "doc": {"_id": "a1"}},
            ]
        }
    )
    with patch("api.db.couchdb_session", return_value=session):
        docs = db.fetch_docs_by_ids("articles", ["a2", "gone", "dead", "a1"])

    assert docs == [{"_id": "a2"}, {"_id": "a1"}]
    args, kwargs = session.request.call_args
    assert args[0] == "POST"
    assert args[1].endswith("articles/_all_docs")
    assert kwargs["json"] == {"keys": ["a2", "gone", "dead", "a1"]}
    assert kwargs["params"] == {"include_docs": "true"}


def test_fetch_by_ids_makes_no_request_for_no_ids():
    session = MagicMock()
    with patch("api.db.couchdb_session", return_value=session):
        assert db.fetch_docs_by_ids("articles", []) == []

    session.request.assert_not_called()


def test_the_search_index_is_created_with_its_design_document():
    """`use_index` names the design document, so the index needs a fixed one."""
    from tasks import init

    with (
        patch("tasks.init.ensure_db"),
        patch("tasks.init._request", return_value=_couch_response({})) as request,
    ):
        init.create_index(
            "articles",
            ["published", "title", "summary", "content"],
            "idx_search_text",
            ddoc="idx_search_text",
        )

    payload = request.call_args.kwargs["json"]
    assert payload["ddoc"] == "idx_search_text"
    assert payload["index"]["fields"] == ["published", "title", "summary", "content"]


# --- Every article is in the search index (tasks/) ---------------------------


@pytest.mark.parametrize(
    "article,expected",
    [
        ({}, ("", "")),
        ({"summary": None, "content": None}, ("", "")),
        ({"summary": "S", "content": 7}, ("S", "")),
        ({"summary": "S", "content": "C"}, ("S", "C")),
    ],
)
def test_a_stored_article_always_has_its_text_fields(article, expected):
    """The search index holds only articles with every text field."""
    from tasks.article_processor import ArticleProcessor

    processor = ArticleProcessor.__new__(ArticleProcessor)
    processor.couchdb_url = "http://couchdb/articles"
    doc = {"title": "T", "link": "https://e/1", "feed_url": "https://e/rss", **article}
    with (
        patch("tasks.article_processor.requests.head") as head,
        patch("tasks.article_processor.requests.post") as post,
        patch("tasks.article_processor.get_default_userspace", return_value=None),
        patch("tasks.article_processor.get_redis_client", return_value=None),
    ):
        head.return_value.status_code = 404
        post.return_value.status_code = 201
        processor.store_article(doc)

    assert post.call_args.kwargs["json"] is doc

    summary, content = expected
    assert doc["summary"] == summary
    assert doc["content"] == content


def _backfill(find_pages: list[list[dict]], bulk_rows: list[list[dict]]):
    """Run the backfill against canned `_find` pages and `_bulk_docs` answers."""
    from tasks import init

    finds, bulks, saved = iter(find_pages), iter(bulk_rows), []

    def request(method, url, **kwargs):
        if url.endswith("_find"):
            return _couch_response({"docs": next(finds)})
        saved.append(kwargs["json"]["docs"])
        return _couch_response(next(bulks))

    with patch("tasks.init._request", side_effect=request) as mocked:
        changed = init.backfill_search_text()
    return changed, saved, mocked


def test_backfill_gives_missing_text_fields_an_empty_string():
    gap = {"_id": "a1", "_rev": "1-x", "title": "T", "summary": "kept"}
    changed, saved, mocked = _backfill([[gap], []], [[{"ok": True, "id": "a1"}]])

    assert changed == 1
    assert saved == [[{**gap, "content": ""}]]
    find = mocked.call_args_list[0].kwargs["json"]
    assert find["use_index"] == "idx_search_gaps"
    assert {"summary": {"$exists": False}} in find["selector"]["$or"]
    assert {"content": {"$exists": False}} in find["selector"]["$or"]


def test_backfill_with_nothing_to_do_writes_nothing():
    changed, saved, _ = _backfill([[]], [])

    assert changed == 0
    assert saved == []


def test_backfill_stops_when_the_articles_cannot_be_saved():
    """Refused by validation: the same articles would come back for ever."""
    gap = {"_id": "a1", "_rev": "1-x", "title": "T"}
    refused = [{"id": "a1", "error": "forbidden"}]
    changed, saved, _ = _backfill([[gap], [gap], [gap]], [refused, refused])

    assert changed == 0
    assert len(saved) == 1


def test_backfill_never_fails_a_start():
    from tasks import init

    with patch(
        "tasks.init._request", side_effect=requests.exceptions.ConnectionError("down")
    ):
        assert init.backfill_search_text() == 0


def test_backfill_replaces_a_value_that_is_not_text():
    """A number or a list cannot be searched and breaks the rendering."""
    gap = {"_id": "a1", "_rev": "1-x", "title": "T", "summary": 7, "content": ["x"]}
    changed, saved, mocked = _backfill([[gap], []], [[{"ok": True, "id": "a1"}]])

    assert changed == 1
    assert saved == [[{**gap, "summary": "", "content": ""}]]
    selector = mocked.call_args_list[0].kwargs["json"]["selector"]
    assert {"summary": {"$not": {"$type": "string"}}} in selector["$or"]
