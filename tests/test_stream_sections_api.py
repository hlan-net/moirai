"""Route tests for ``GET /api/stream.rss?section=`` (#266)."""

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault(
    "JWT_SECRET_KEY", "super_secret_test_key_that_is_at_least_32_chars_long"
)
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password_123")

import pytest  # noqa: E402

from api.validation import FeedUpdateRequest  # noqa: E402
from main import app  # noqa: E402

ARTICLE = {
    "_id": "a1",
    "title": "Derby Result",
    "link": "https://www.hs.fi/urheilu/art-1.html",
    "summary": "S",
    "published": "2024-01-01T10:00:00+00:00",
    "feed_url": "https://www.hs.fi/rss/tuoreimmat.xml",
    "section": "sports",
}


@pytest.fixture
def client():
    redis = MagicMock()
    redis.get.return_value = None
    with patch("api.routes.get_public_read_setting", return_value=True), patch(
        "api.routes.query_couchdb", return_value=[ARTICLE]
    ) as query, patch("api.routes.fetch_from_couchdb", return_value=[]), patch(
        "api.routes.enrich_articles_with_issues"
    ), patch(
        "api.routes.get_redis_client", return_value=redis
    ):
        yield app.test_client(), query, redis


def test_without_section_is_unchanged(client):
    test_client, query, redis = client
    res = test_client.get("/api/stream.rss")
    assert res.status_code == 200
    selector = query.call_args.kwargs["selector"]
    assert "section" not in selector
    assert redis.setex.call_args.args[0] == "stream_rss_xml"
    body = res.get_data(as_text=True)
    assert "<title>Moirai Aggregated Stream</title>" in body
    assert '<category domain="section">sports</category>' in body


def test_section_filters_and_caches_per_section(client):
    test_client, query, redis = client
    res = test_client.get("/api/stream.rss?section=sports")
    assert res.status_code == 200
    selector = query.call_args.kwargs["selector"]
    assert selector["section"] == "sports"
    assert "published" in selector
    assert redis.get.call_args.args[0] == "stream_rss_xml:sports"
    assert redis.setex.call_args.args[0] == "stream_rss_xml:sports"
    assert "Sports" in res.get_data(as_text=True)


def test_cache_hit_is_served_per_section(client):
    test_client, query, redis = client
    redis.get.return_value = "<rss>cached</rss>"
    res = test_client.get("/api/stream.rss?section=culture")
    assert res.status_code == 200
    assert res.get_data(as_text=True) == "<rss>cached</rss>"
    assert redis.get.call_args.args[0] == "stream_rss_xml:culture"
    query.assert_not_called()


def test_invalid_section_is_rejected(client):
    test_client, query, _ = client
    res = test_client.get("/api/stream.rss?section=news")
    assert res.status_code == 400
    query.assert_not_called()


def test_feed_update_accepts_category():
    assert FeedUpdateRequest(title="HS", category="sports").category == "sports"
    assert FeedUpdateRequest(title="HS").category is None
    assert FeedUpdateRequest(title="HS", category="<b>sports</b>").category == "sports"
