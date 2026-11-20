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
    with (
        patch("api.routes.get_public_read_setting", return_value=True),
        patch("api.routes.query_couchdb", return_value=[ARTICLE]) as query,
        patch("api.routes.fetch_from_couchdb", return_value=[]),
        patch("api.routes.enrich_articles_with_issues"),
        patch("api.routes.get_redis_client", return_value=redis),
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


def test_feed_update_category_alone_leaves_title_untouched():
    # A section change sends only the category; re-sending the title would
    # escape it again on every change (``&amp;`` -> ``&amp;amp;``).
    validated = FeedUpdateRequest(category="culture")
    assert validated.title is None
    assert validated.category == "culture"


def test_feed_update_rejects_empty_title():
    with pytest.raises(ValueError):
        FeedUpdateRequest(title="", category="culture")


def _admin_headers() -> dict:
    import base64

    creds = base64.b64encode(
        f"{os.environ['ADMIN_USERNAME']}:{os.environ['ADMIN_PASSWORD']}".encode()
    ).decode()
    return {"Authorization": f"Basic {creds}"}


@pytest.mark.parametrize(
    "stored, sent, refiled",
    [
        ("sports", "general", True),  # moved back: articles must leave Sports
        ("general", "culture", True),
        ("sports", "sports", False),  # unchanged: nothing to re-file
    ],
)
def test_feed_category_change_refiles_existing_articles(stored, sent, refiled):
    feed = {
        "_id": "f1",
        "url": "https://www.hs.fi/rss/urheilu.xml",
        "original_url": "https://hs.fi/rss/urheilu.xml",
        "title": "HS Urheilu",
        "category": stored,
    }
    with (
        patch("api.routes.fetch_from_couchdb", return_value=dict(feed)),
        patch("api.routes.update_couchdb_doc", return_value=True),
        patch("api.routes.invalidate_feed_mappings_cache"),
        patch("api.routes.backfill_sections.start_feed_refile") as refile,
        patch("api.auth.get_user_by_email", return_value=None),
    ):
        res = app.test_client().put(
            "/api/feeds/f1", json={"category": sent}, headers=_admin_headers()
        )
    assert res.status_code == 200, res.get_data(as_text=True)
    assert res.get_json()["title"] == "HS Urheilu"
    if refiled:
        refile.assert_called_once_with([feed["url"], feed["original_url"]])
    else:
        refile.assert_not_called()


def test_feed_url_and_category_change_refiles_the_replaced_url_too():
    feed = {
        "_id": "f1",
        "url": "https://www.hs.fi/rss/urheilu.xml",
        "original_url": "https://hs.fi/rss/urheilu.xml",
        "title": "HS Urheilu",
        "category": "sports",
    }
    with (
        patch("api.routes.fetch_from_couchdb", return_value=dict(feed)),
        patch("api.routes.update_couchdb_doc", return_value=True),
        patch("api.routes.invalidate_feed_mappings_cache"),
        patch("api.routes.backfill_sections.start_feed_refile") as refile,
        patch("api.auth.get_user_by_email", return_value=None),
    ):
        res = app.test_client().put(
            "/api/feeds/f1",
            json={"category": "general", "new_url": "https://www.hs.fi/rss/sport.xml"},
            headers=_admin_headers(),
        )
    assert res.status_code == 200, res.get_data(as_text=True)
    refile.assert_called_once_with(
        ["https://www.hs.fi/rss/sport.xml", feed["url"], feed["original_url"]]
    )


def test_feed_update_request_needs_at_least_one_field():
    from pydantic import ValidationError

    from api.validation import FeedUpdateRequest

    with pytest.raises(ValidationError):
        FeedUpdateRequest()
    with pytest.raises(ValidationError):
        FeedUpdateRequest.model_validate({"tittle": "HS"})
    assert FeedUpdateRequest(category="sports").category == "sports"


# ── Cache covers the Stream page's limit too (#308) ───────────────────────────


def test_stream_page_limit_is_served_from_cache(client):
    test_client, query, redis = client
    redis.get.return_value = "<rss>cached</rss>"
    res = test_client.get("/api/stream.rss?limit=200&section=sports")
    assert res.get_data(as_text=True) == "<rss>cached</rss>"
    assert redis.get.call_args.args[0] == "stream_rss_xml:sports@200"
    query.assert_not_called()


def test_stream_page_limit_fills_its_own_cache_key(client):
    test_client, _query, redis = client
    assert test_client.get("/api/stream.rss?limit=200").status_code == 200
    assert redis.setex.call_args.args[0] == "stream_rss_xml@200"


def test_other_limits_stay_uncached(client):
    test_client, query, redis = client
    assert test_client.get("/api/stream.rss?limit=50&section=main").status_code == 200
    redis.get.assert_not_called()
    redis.setex.assert_not_called()
    query.assert_called_once()


def test_every_cached_stream_key_is_invalidated():
    from tasks.sections import (
        SECTIONS,
        STREAM_CACHE_KEYS,
        STREAM_CACHED_LIMITS,
        stream_cache_key,
    )

    assert 200 in STREAM_CACHED_LIMITS  # RSS_LIMIT in ui/src/components/StreamPage.vue
    for section in (None, *SECTIONS):
        for limit in STREAM_CACHED_LIMITS:
            assert stream_cache_key(section, limit) in STREAM_CACHE_KEYS
    assert stream_cache_key("sports", 100) == "stream_rss_xml:sports"
    assert stream_cache_key(None, 100) == "stream_rss_xml"
    assert stream_cache_key("sports", 50) is None
