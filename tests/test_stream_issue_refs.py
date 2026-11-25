"""Issues of an article in ``/api/stream.rss``, and the chat sessions of a subject (#376).

The Stream page's side column opens an event or a trend from an article, so
the feed carries each issue's id; and it continues the conversation of an
article or an issue, so the chat history can be asked for one subject.
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
from flask import g  # noqa: E402

from api.rss_ops import MOIRAI_RSS_NS, generate_rss_item_xml  # noqa: E402
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

ISSUES = [
    {"id": "ev-1", "logos": "Derby & aftermath", "longevity": "transient"},
    {"id": "tr-1", "logos": "League finances", "longevity": "temporal"},
    {"id": "ep-1", "logos": "Football in Finland", "longevity": "epic"},
    {"id": "x-1", "logos": "", "longevity": "transient"},
]


def _parse(dt: str):
    from datetime import datetime

    return datetime.fromisoformat(dt)


def _item(article: dict) -> ET.Element:
    xml = (
        f'<rss xmlns:moirai="{MOIRAI_RSS_NS}">'
        f"{generate_rss_item_xml(article, {}, _parse)}</rss>"
    )
    return ET.fromstring(xml).find("item")


def _refs(item: ET.Element) -> list[tuple[str, str, str | None]]:
    return [
        (c.get("domain"), c.text, c.get(f"{{{MOIRAI_RSS_NS}}}id"))
        for c in item.findall("category")
        if c.get("domain") in ("event", "trend")
    ]


def test_issues_become_event_and_trend_categories_with_ids():
    item = _item({**ARTICLE, "issues": ISSUES})

    assert _refs(item) == [
        ("event", "Derby & aftermath", "ev-1"),
        ("trend", "League finances", "tr-1"),
        ("trend", "Football in Finland", "ep-1"),
    ]


def test_article_without_issues_has_no_event_or_trend_category():
    assert _refs(_item(ARTICLE)) == []
    assert _refs(_item({**ARTICLE, "issues": None})) == []


def test_issue_without_an_id_keeps_its_name():
    item = _item({**ARTICLE, "issues": [{"logos": "Nameless id"}]})
    assert _refs(item) == [("event", "Nameless id", None)]


def test_feed_with_issue_ids_is_well_formed_and_declares_the_namespace():
    def with_issues(articles):
        for article in articles:
            article["issues"] = ISSUES

    redis = MagicMock()
    redis.get.return_value = None
    with (
        patch("api.routes.get_public_read_setting", return_value=True),
        patch("api.routes.query_couchdb", return_value=[dict(ARTICLE)]),
        patch("api.routes.fetch_from_couchdb", return_value=[]),
        patch("api.routes.enrich_articles_with_issues", side_effect=with_issues),
        patch("api.routes.get_redis_client", return_value=redis),
    ):
        res = app.test_client().get("/api/stream.rss?limit=200&section=sports")

    assert res.status_code == 200
    root = ET.fromstring(res.get_data(as_text=True))  # raises if malformed
    item = root.find("channel").find("item")
    assert ("event", "Derby & aftermath", "ev-1") in _refs(item)


# ── Reading one issue follows the public-read setting ─────────────────────────


def test_issue_detail_needs_a_login_when_public_read_is_off():
    with (
        patch("api.routes.get_public_read_setting", return_value=False),
        patch("api.routes.verify_jwt_in_request", return_value=(False, "no")),
        patch("api.routes.fetch_from_couchdb") as fetch,
    ):
        res = app.test_client().get("/api/issues/ev-1")

    assert res.status_code == 401
    fetch.assert_not_called()


@pytest.mark.parametrize("public_read,logged_in", [(True, False), (False, True)])
def test_issue_detail_is_served_to_a_reader_who_may_read(public_read, logged_in):
    with (
        patch("api.routes.get_public_read_setting", return_value=public_read),
        patch("api.routes.verify_jwt_in_request", return_value=(logged_in, "")),
        patch("api.routes.fetch_from_couchdb", return_value={"_id": "ev-1"}),
    ):
        res = app.test_client().get("/api/issues/ev-1")

    assert res.status_code == 200
    assert res.get_json() == {"_id": "ev-1"}


# ── Chat sessions of one subject ──────────────────────────────────────────────


@pytest.fixture
def chat_client():
    def fake_verify():
        g.user_id = "u1"
        g.user_role = "user"
        return True, ""

    sessions = [
        {"_id": "s-old", "created_at": "2026-11-01T10:00:00+00:00"},
        {"_id": "s-new", "created_at": "2026-11-20T10:00:00+00:00"},
    ]
    # Patch the namespace of the view the app actually serves, not the module
    # attribute: a reload of api.chat_routes (tests/test_chat_routes_refactor.py)
    # must not be able to separate the two.
    view = next(
        fn
        for endpoint, fn in app.view_functions.items()
        if endpoint.endswith(".list_chat_history")
    )
    route_globals = getattr(view, "__wrapped__", view).__globals__
    query = MagicMock(return_value=sessions)
    with (
        patch("api.auth.verify_request_auth", side_effect=fake_verify),
        patch.dict(route_globals, {"query_couchdb": query}),
    ):
        yield app.test_client(), query


def test_chat_history_of_a_subject_filters_and_sorts_newest_first(chat_client):
    client, query = chat_client
    res = client.get(
        "/api/chat/history?context_type=issue&entity_id=ev-1",
    )

    assert res.status_code == 200
    assert [s["_id"] for s in res.get_json()] == ["s-new", "s-old"]
    assert query.call_args.args == (
        "chat_history",
        {"user_id": "u1", "context.type": "issue", "context.entity_id": "ev-1"},
    )


def test_chat_history_without_a_subject_is_the_callers_whole_history(chat_client):
    client, query = chat_client
    res = client.get("/api/chat/history")

    assert res.status_code == 200
    assert query.call_args.args == ("chat_history", {"user_id": "u1"})


@pytest.mark.parametrize("query_string", ["context_type=issue", "entity_id=ev-1"])
def test_chat_history_needs_both_parts_of_a_subject(chat_client, query_string):
    client, query = chat_client
    res = client.get(f"/api/chat/history?{query_string}")

    assert res.status_code == 400
    query.assert_not_called()
