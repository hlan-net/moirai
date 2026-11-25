"""No route reads the whole ``articles`` database (#369).

``/api/mythology`` loaded every article with its body to count them, which took
an API pod past its memory limit. These tests pin the replacements: document
counts, a query for public issues, a bounded ``/mcp/articles`` query behind
admin auth, and the guard in ``fetch_from_couchdb``.
"""

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault(
    "JWT_SECRET_KEY", "super_secret_test_key_that_is_at_least_32_chars_long"
)
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password_123")

import pytest  # noqa: E402
from flask import g  # noqa: E402

from api import db  # noqa: E402
from api.telemetry import _span_exporter  # noqa: E402
from main import app  # noqa: E402

PUBLIC_ISSUE = {
    "_id": "i1",
    "logos": "Clotho spins",
    "description": "D",
    "longevity": "temporal",
    "status": "active",
    "born_at": "2026-11-01T00:00:00+00:00",
    "premises": [{"a": 1}, {"b": 2}],
}


def _response(status: int, payload: dict) -> MagicMock:
    res = MagicMock()
    res.status_code = status
    res.json.return_value = payload
    if status >= 400:
        res.raise_for_status.side_effect = db.requests.exceptions.HTTPError(
            response=res
        )
    return res


# ---------------------------------------------------------------------------
# /api/mythology
# ---------------------------------------------------------------------------


def test_mythology_counts_and_queries_without_full_reads():
    counts = {"feeds": 12, "articles": 29814, "issues": 40}
    with (
        patch("api.routes.query_couchdb", return_value=[PUBLIC_ISSUE]) as query,
        patch("api.routes.count_docs", side_effect=counts.get) as count,
        patch("api.routes.fetch_from_couchdb") as fetch,
    ):
        res = app.test_client().get("/api/mythology")

    assert res.status_code == 200
    body = res.get_json()
    assert body["stats"] == counts
    assert body["public_issues"] == [
        {
            "_id": "i1",
            "logos": "Clotho spins",
            "description": "D",
            "longevity": "temporal",
            "status": "active",
            "born_at": "2026-11-01T00:00:00+00:00",
            "premises_count": 2,
        }
    ]
    fetch.assert_not_called()
    assert {c.args[0] for c in count.call_args_list} == set(counts)
    assert query.call_args.args[0] == "issues"
    assert query.call_args.kwargs["selector"] == {"public": True}
    assert query.call_args.kwargs["limit"] > 0


def test_mythology_defaults_when_couchdb_is_down():
    with (
        patch("api.routes.query_couchdb", return_value=[]),
        patch("api.routes.count_docs", return_value=None),
    ):
        res = app.test_client().get("/api/mythology")

    assert res.status_code == 200
    assert res.get_json() == {
        "stats": {"feeds": 0, "articles": 0, "issues": 0},
        "public_issues": [],
    }


# ---------------------------------------------------------------------------
# api.db helpers
# ---------------------------------------------------------------------------


def test_count_docs_subtracts_design_docs_and_reads_no_documents():
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/_design_docs"):
            return _response(200, {"rows": [{"id": "_design/a"}, {"id": "_design/b"}]})
        return _response(200, {"doc_count": 102})

    with (
        patch("api.db.get_couchdb_uri", return_value="http://couch/"),
        patch("api.db._request", side_effect=fake_request),
    ):
        assert db.count_docs("articles") == 100

    assert [c[1] for c in calls] == [
        "http://couch/articles",
        "http://couch/articles/_design_docs",
    ]
    assert all("include_docs" not in str(c[2]) for c in calls)


def test_count_docs_missing_db_is_zero_and_unreachable_is_none():
    with (
        patch("api.db.get_couchdb_uri", return_value="http://couch/"),
        patch("api.db._request", return_value=_response(404, {})),
    ):
        assert db.count_docs("feeds") == 0

    with (
        patch("api.db.get_couchdb_uri", return_value="http://couch/"),
        patch(
            "api.db._request",
            side_effect=db.requests.exceptions.ConnectionError("down"),
        ),
    ):
        assert db.count_docs("feeds") is None


def test_fetch_from_couchdb_refuses_whole_articles_db():
    with patch("api.db._request") as request:
        with pytest.raises(ValueError, match="articles"):
            db.fetch_from_couchdb("articles")
    request.assert_not_called()


def test_fetch_from_couchdb_still_reads_single_articles():
    with (
        patch("api.db.get_couchdb_uri", return_value="http://couch/"),
        patch("api.db._request", return_value=_response(200, {"_id": "a1"})) as req,
    ):
        assert db.fetch_from_couchdb("articles", "a1") == {"_id": "a1"}
    assert req.call_args.args[1] == "http://couch/articles/a1"


# ---------------------------------------------------------------------------
# /mcp routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/mcp/articles"),
        ("get", "/mcp/events?userspace=x"),
        ("post", "/mcp/events"),
        ("get", "/mcp/trends?userspace=x"),
        ("post", "/mcp/trends"),
    ],
)
def test_mcp_routes_require_auth(method, path):
    with (
        patch("api.mcp_routes.verify_request_auth", return_value=(False, "nope")),
        patch("api.mcp_routes.query_couchdb") as query,
        patch("api.mcp_routes.store_to_couchdb") as store,
    ):
        res = getattr(app.test_client(), method)(path, json={})

    assert res.status_code == 401
    query.assert_not_called()
    store.assert_not_called()


def _authenticated_as(role: str):
    def fake_verify():
        g.user_id = "u1"
        g.user_role = role
        return True, ""

    return fake_verify


@pytest.mark.parametrize("path", ["/mcp/articles", "/mcp/events?userspace=x"])
def test_mcp_routes_require_admin(path):
    with (
        patch(
            "api.mcp_routes.verify_request_auth", side_effect=_authenticated_as("user")
        ),
        patch("api.mcp_routes.query_couchdb") as query,
    ):
        res = app.test_client().get(path)

    assert res.status_code == 403
    query.assert_not_called()


@pytest.fixture
def authed_articles():
    with (
        patch(
            "api.mcp_routes.verify_request_auth", side_effect=_authenticated_as("admin")
        ),
        patch("api.mcp_routes.query_couchdb", return_value=[{"_id": "a1"}]) as query,
    ):
        yield app.test_client(), query


def test_mcp_articles_is_a_bounded_query(authed_articles):
    client, query = authed_articles
    res = client.get("/mcp/articles")

    assert res.status_code == 200
    assert res.get_json() == [{"_id": "a1"}]
    assert query.call_args.args[0] == "articles"
    assert query.call_args.kwargs["selector"] == {"published": {"$gt": None}}
    assert query.call_args.kwargs["sort"] == [{"published": "desc"}]
    assert query.call_args.kwargs["limit"] == 100


def test_mcp_articles_since_goes_into_the_selector_as_utc(authed_articles):
    client, query = authed_articles
    res = client.get("/mcp/articles?since=2026-11-24T12:00:00%2B02:00&limit=5")

    assert res.status_code == 200
    assert query.call_args.kwargs["selector"] == {
        "published": {"$gte": "2026-11-24T10:00:00+00:00"}
    }
    assert query.call_args.kwargs["limit"] == 5


@pytest.mark.parametrize(
    "query_string",
    ["since=yesterday", "limit=0", "limit=1001", "limit=lots"],
)
def test_mcp_articles_rejects_bad_parameters(authed_articles, query_string):
    client, query = authed_articles
    res = client.get(f"/mcp/articles?{query_string}")

    assert res.status_code == 400
    query.assert_not_called()


# ---------------------------------------------------------------------------
# Span exporter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("none", None),
        ("console", "ConsoleSpanExporter"),
        ("OTLP", "OTLPSpanExporter"),
        ("jaeger", None),
    ],
)
def test_span_exporter_follows_otel_traces_exporter(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("OTEL_TRACES_EXPORTER", raising=False)
    else:
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", value)

    exporter = _span_exporter()

    assert (type(exporter).__name__ if exporter else None) == expected
