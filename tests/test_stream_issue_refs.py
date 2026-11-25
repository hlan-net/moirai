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


# ── A trend reaches an article through its events ─────────────────────────────


def test_parent_issues_are_attached_to_the_articles_of_their_events():
    from api.enrichment import _build_article_issue_map

    event = {
        "_id": "ev-1",
        "logos": "Derby aftermath",
        "longevity": "transient",
        "premises": [
            {"type": "message", "id": "https://example.com/a"},
            {"type": "message", "id": "https://example.com/b"},
        ],
    }
    other_event = {
        "_id": "ev-2",
        "logos": "Transfer window",
        "longevity": "transient",
        "premises": [{"type": "message", "id": "https://example.com/c"}],
    }
    trend = {
        "_id": "tr-1",
        "logos": "League finances",
        "longevity": "temporal",
        # Holds the event twice over (as a premise, and one article directly):
        # the article must list the trend once.
        "premises": [
            {"type": "issue", "id": "ev-1"},
            {"type": "message", "id": "https://example.com/a"},
        ],
    }

    mapping = _build_article_issue_map([event, other_event, trend], [trend])

    assert [i["id"] for i in mapping["https://example.com/a"]] == ["ev-1", "tr-1"]
    assert [i["id"] for i in mapping["https://example.com/b"]] == ["ev-1", "tr-1"]
    assert [i["id"] for i in mapping["https://example.com/c"]] == ["ev-2"]


def test_parent_issues_are_queried_by_the_ids_of_the_direct_issues():
    from api.enrichment import _fetch_parent_issues

    with patch("api.enrichment.query_couchdb", return_value=[]) as query:
        assert _fetch_parent_issues([]) == []
        query.assert_not_called()

        _fetch_parent_issues([{"_id": "ev-1"}, {"_id": "ev-2"}])

    selector = query.call_args.kwargs["selector"]
    assert selector == {
        "premises": {"$elemMatch": {"type": "issue", "id": {"$in": ["ev-1", "ev-2"]}}}
    }


def test_issue_detail_expands_its_nested_issues_on_request():
    docs = {
        "tr-1": {
            "_id": "tr-1",
            "logos": "League finances",
            "longevity": "temporal",
            "premises": [
                {"type": "issue", "id": "ev-1"},
                {"type": "issue", "id": "gone"},
                {"type": "issue", "id": "../bad id"},
                {"type": "message", "id": "https://example.com/direct"},
            ],
        },
        "ev-1": {
            "_id": "ev-1",
            "logos": "Derby aftermath",
            "longevity": "transient",
            "premises": [
                {"type": "message", "id": "https://example.com/a"},
                {"type": "issue", "id": "deeper"},
            ],
        },
    }
    with (
        patch("api.routes.get_public_read_setting", return_value=True),
        patch("api.routes.fetch_from_couchdb", side_effect=lambda db, i: docs.get(i)),
    ):
        plain = app.test_client().get("/api/issues/tr-1")
        expanded = app.test_client().get("/api/issues/tr-1?expand=issues")

    assert "nested_issues" not in plain.get_json()
    assert expanded.status_code == 200
    assert expanded.get_json()["nested_issues"] == [
        {
            "id": "ev-1",
            "logos": "Derby aftermath",
            "longevity": "transient",
            "article_links": ["https://example.com/a"],
        }
    ]


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


# ── An issue of another userspace ─────────────────────────────────────────────

OTHER = {"_id": "ev-9", "logos": "Elsewhere", "userspace": "other-space"}
DEFAULT = {"_id": "ev-1", "logos": "Here", "userspace": "default-space"}


def _get_issue(issue_id, *, logged_in, may_access, path_suffix=""):
    def fake_verify():
        if logged_in:
            g.user_id = "u1"
            g.user_role = "user"
        return logged_in, ""

    docs = {
        "ev-9": OTHER,
        "ev-1": DEFAULT,
        "tr-1": {
            "_id": "tr-1",
            "userspace": "default-space",
            "premises": [
                {"type": "issue", "id": "ev-1"},
                {"type": "issue", "id": "ev-9"},
            ],
        },
    }
    with (
        patch("api.routes.get_public_read_setting", return_value=True),
        patch("api.routes.verify_jwt_in_request", side_effect=fake_verify),
        patch("api.routes.get_default_userspace", return_value="default-space"),
        patch("api.routes.can_access_userspace", return_value=may_access) as access,
        patch("api.routes.fetch_from_couchdb", side_effect=lambda db, i: docs.get(i)),
    ):
        res = app.test_client().get(f"/api/issues/{issue_id}{path_suffix}")
    return res, access


def test_issue_of_the_default_userspace_is_readable_without_an_ownership_check():
    res, access = _get_issue("ev-1", logged_in=False, may_access=False)
    assert res.status_code == 200
    access.assert_not_called()


@pytest.mark.parametrize(
    "logged_in,may_access,status",
    [(False, True, 404), (True, False, 404), (True, True, 200)],
)
def test_issue_of_another_userspace_needs_a_caller_who_may_use_it(
    logged_in, may_access, status
):
    res, access = _get_issue("ev-9", logged_in=logged_in, may_access=may_access)

    assert res.status_code == status
    if logged_in:
        assert access.call_args.args == ("other-space", "u1", "user")


def test_nested_issues_of_another_userspace_are_left_out():
    res, _ = _get_issue(
        "tr-1", logged_in=True, may_access=False, path_suffix="?expand=issues"
    )

    assert res.status_code == 200
    assert [n["id"] for n in res.get_json()["nested_issues"]] == ["ev-1"]


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
