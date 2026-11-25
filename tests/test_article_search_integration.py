"""Article search against a real CouchDB (#387).

The unit tests pin the shape of the request. These pin what CouchDB does with
it: that it chooses the search index and loads no document, that a match in
each text field is found newest first, and that a search still answers when
the index is missing, and that an article without a text field is repaired
at start-up and then found.

Needs a throwaway CouchDB of the supported version, named by
``SEARCH_TEST_COUCHDB_URI`` (with credentials, ending in ``/``)::

    docker run -d --rm -p 127.0.0.1:15984:5984 \\
        -e COUCHDB_USER=admin -e COUCHDB_PASSWORD=test couchdb:3.5.3
    SEARCH_TEST_COUCHDB_URI=http://admin:test@127.0.0.1:15984/ \\
        pytest -m integration tests/test_article_search_integration.py

The tests write to the ``articles`` database. They fail rather than run when
it already holds documents that they did not write. Without the variable they
are skipped; CI sets it for the CouchDB service of the ``test`` job.
"""

import os
from unittest.mock import patch

os.environ.setdefault(
    "JWT_SECRET_KEY", "super_secret_test_key_that_is_at_least_32_chars_long"
)
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password_123")

import pytest  # noqa: E402
import requests  # noqa: E402

from api.db_constants import (  # noqa: E402
    ARTICLE_SEARCH_GAPS_INDEX,
    ARTICLE_SEARCH_GAPS_SELECTOR,
    ARTICLE_SEARCH_INDEX,
    ARTICLE_SEARCH_INDEX_FIELDS,
)

pytestmark = pytest.mark.integration

COUCHDB = os.environ.get("SEARCH_TEST_COUCHDB_URI", "")
MARKER_ID = "search-integration-marker"

ARTICLES = [
    # id, published, title, summary, content
    ("s1", "2026-11-01T10:00:00+00:00", "Zebra in the title", "nothing", "nothing"),
    ("s2", "2026-11-03T10:00:00+00:00", "Plain", "a ZEBRA in the summary", "nothing"),
    ("s3", "2026-11-02T10:00:00+00:00", "Plain", "nothing", "the content has a zebra"),
    ("s4", "2026-11-04T10:00:00+00:00", "Plain", "nothing", "nothing"),
    ("s5", "2026-11-05T10:00:00+00:00", "100% (sure)", "a.b", "nothing"),
]


def _index_ddoc() -> str:
    return f"{COUCHDB}articles/_design/{ARTICLE_SEARCH_INDEX}"


def _drop_index() -> None:
    res = requests.get(_index_ddoc(), timeout=10)
    if res.ok:
        requests.delete(
            _index_ddoc(), params={"rev": res.json()["_rev"]}, timeout=10
        ).raise_for_status()


def _create_index() -> None:
    from tasks import init

    with patch("tasks.init.ensure_db"):
        init.create_index(
            "articles",
            ARTICLE_SEARCH_INDEX_FIELDS,
            ARTICLE_SEARCH_INDEX,
            ddoc=ARTICLE_SEARCH_INDEX,
        )


@pytest.fixture(scope="module")
def couchdb():
    """The article fixtures in a database that only these tests write to."""
    if not COUCHDB:
        pytest.skip("SEARCH_TEST_COUCHDB_URI is not set")
    # Naming a CouchDB is asking for these tests: from here on a problem is a
    # failure, not a skip that would pass unnoticed in CI.
    requests.get(f"{COUCHDB}_up", timeout=3).raise_for_status()

    for name in ("_users", "_replicator", "articles"):
        requests.put(f"{COUCHDB}{name}", timeout=10)
    info = requests.get(f"{COUCHDB}articles", timeout=10).json()
    marked = requests.get(f"{COUCHDB}articles/{MARKER_ID}", timeout=10).ok
    if info.get("doc_count", 0) > 0 and not marked:
        pytest.fail("the articles database holds documents these tests did not write")

    docs = [{"_id": MARKER_ID}] + [
        {
            "_id": doc_id,
            "published": published,
            "title": title,
            "summary": summary,
            "content": content,
            "link": f"https://example.com/{doc_id}",
            "feed_url": "https://example.com/rss",
        }
        for doc_id, published, title, summary, content in ARTICLES
    ]
    for doc in docs:
        existing = requests.get(f"{COUCHDB}articles/{doc['_id']}", timeout=10)
        if existing.ok:
            doc["_rev"] = existing.json()["_rev"]
    requests.post(
        f"{COUCHDB}articles/_bulk_docs", json={"docs": docs}, timeout=10
    ).raise_for_status()

    with (
        patch("api.db.get_couchdb_uri", return_value=COUCHDB),
        patch("tasks.init.get_couchdb_uri", return_value=COUCHDB),
    ):
        from tasks import init

        # The index every deployment has had since before the search index;
        # the sort falls back to it when the search index is missing.
        with patch("tasks.init.ensure_db"):
            init.create_index("articles", ["published"], "published-index")
        _create_index()
        yield


@pytest.fixture
def client(couchdb):
    from main import app

    with (
        patch("api.auth.verify_request_auth", return_value=(True, "")),
        patch("api.routes.fetch_from_couchdb", return_value=[]),
        patch("api.routes.enrich_articles_with_issues"),
    ):
        yield app.test_client()


def _ids(client, query: str) -> list[str]:
    res = client.get("/api/articles/search", query_string={"q": query})
    assert res.status_code == 200, res.get_data(as_text=True)
    return [result["_id"] for result in res.get_json()["results"]]


def test_a_match_in_each_field_is_found_newest_first(client):
    assert _ids(client, "zebra") == ["s2", "s3", "s1"]


def test_no_match_is_an_empty_result(client):
    assert _ids(client, "giraffe") == []


def test_the_text_is_matched_literally(client):
    assert _ids(client, "100% (sure)") == ["s5"]
    # A dot is a dot, not "any character".
    assert _ids(client, "a.b") == ["s5"]
    assert _ids(client, "a-b") == []


def test_couchdb_answers_from_the_search_index_without_loading_documents(client):
    """The point of #387: the query the route sends is covered by the index."""
    from main import app
    from api.routes import _search_selector

    with app.test_request_context("/api/articles/search?q=zebra"):
        selector = _search_selector("zebra")
    query = {
        "selector": selector,
        "fields": ["_id", "published"],
        "sort": [{"published": "desc"}],
        "use_index": ARTICLE_SEARCH_INDEX,
        "limit": 200,
    }

    plan = requests.post(f"{COUCHDB}articles/_explain", json=query, timeout=10).json()
    assert plan["index"]["ddoc"] == f"_design/{ARTICLE_SEARCH_INDEX}"
    assert plan.get("covering") is True

    found = requests.post(
        f"{COUCHDB}articles/_find", json={**query, "execution_stats": True}, timeout=10
    ).json()
    assert [doc["_id"] for doc in found["docs"]] == ["s2", "s3", "s1"]
    assert found["execution_stats"]["total_docs_examined"] == 0


def test_an_article_without_a_text_field_is_backfilled_and_found(client):
    """An article outside the search index is listed, repaired and searchable.

    A Mango index holds only documents that have every indexed field, so this
    article cannot be found before the backfill, not even by its title.
    """
    from tasks import init

    for doc_id in ("gap1", "gap2"):
        existing = requests.get(f"{COUCHDB}articles/{doc_id}", timeout=10)
        if existing.ok:
            requests.delete(
                f"{COUCHDB}articles/{doc_id}",
                params={"rev": existing.json()["_rev"]},
                timeout=10,
            )
    gaps = [
        # No summary at all; a null content.
        {"_id": "gap1", "published": "2026-11-06T10:00:00+00:00", "title": "Okapi"},
        {
            "_id": "gap2",
            "published": "2026-11-07T10:00:00+00:00",
            "title": "Plain",
            "summary": "an okapi here",
            "content": None,
        },
    ]
    requests.post(
        f"{COUCHDB}articles/_bulk_docs", json={"docs": gaps}, timeout=10
    ).raise_for_status()
    with patch("tasks.init.ensure_db"):
        init.create_index(
            "articles",
            ["published"],
            ARTICLE_SEARCH_GAPS_INDEX,
            ddoc=ARTICLE_SEARCH_GAPS_INDEX,
            partial_filter=ARTICLE_SEARCH_GAPS_SELECTOR,
        )
    assert _ids(client, "okapi") == []
    complete_before = requests.get(f"{COUCHDB}articles/s1", timeout=10).json()["_rev"]

    assert init.backfill_search_text() == 2

    assert _ids(client, "okapi") == ["gap2", "gap1"]
    repaired = requests.get(f"{COUCHDB}articles/gap1", timeout=10).json()
    assert (repaired["summary"], repaired["content"]) == ("", "")
    # What was there is kept.
    kept = requests.get(f"{COUCHDB}articles/gap2", timeout=10).json()
    assert (kept["summary"], kept["content"]) == ("an okapi here", "")
    # Nothing is left to do, and complete articles were not touched.
    assert init.backfill_search_text() == 0
    complete_after = requests.get(f"{COUCHDB}articles/s1", timeout=10).json()["_rev"]
    assert complete_after == complete_before


def test_a_search_still_answers_when_the_index_is_missing(client):
    """CouchDB falls back to the `published` index and loads the documents."""
    _drop_index()
    try:
        assert _ids(client, "zebra") == ["s2", "s3", "s1"]
    finally:
        _create_index()
