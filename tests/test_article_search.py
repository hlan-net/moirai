"""``GET /api/articles/search`` (#377): the Stream page's search.

The route answers with the items of ``/api/stream.rss`` when asked for
``format=rss``, so the page shows the results as its own rows.
"""

import os
import xml.etree.ElementTree as ET
from unittest.mock import patch

os.environ.setdefault(
    "JWT_SECRET_KEY", "super_secret_test_key_that_is_at_least_32_chars_long"
)
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password_123")

import pytest  # noqa: E402
import requests  # noqa: E402

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
    """A logged-in client and the mocked article query."""
    with (
        patch("api.auth.verify_request_auth", return_value=(True, "")),
        patch("api.routes.query_couchdb", return_value=[dict(ARTICLE)]) as query,
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
