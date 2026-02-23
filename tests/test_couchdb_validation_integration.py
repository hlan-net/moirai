import uuid

import pytest
import requests

from api.db_config import get_couchdb_uri
from tasks.init import (
    ARTICLE_STATS_VIEWS,
    ARTICLE_VALIDATE_DOC,
    FEED_HEALTH_VIEWS,
    FEED_VALIDATE_DOC,
    ensure_design_doc,
)


def _couchdb_ready() -> bool:
    try:
        response = requests.get(get_couchdb_uri(), timeout=2)
    except requests.RequestException:
        return False
    return response.status_code < 400


def _ensure_test_db(db_name: str) -> bool:
    try:
        response = requests.put(f"{get_couchdb_uri()}{db_name}", timeout=5)
    except requests.RequestException:
        return False

    if response.status_code in (200, 201, 202, 412):
        return True

    return False


def _delete_db(db_name: str) -> None:
    try:
        requests.delete(f"{get_couchdb_uri()}{db_name}", timeout=5)
    except requests.RequestException:
        pass


def _insert_docs(base_url: str, docs: list[dict]) -> None:
    for doc in docs:
        response = requests.post(base_url, json=doc, timeout=5)
        assert response.status_code in (200, 201)


def _fetch_view(base_url: str, design_doc: str, view: str, params: dict) -> dict:
    response = requests.get(
        f"{base_url}/_design/{design_doc}/_view/{view}",
        params=params,
        timeout=5,
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.integration
def test_article_validate_doc_update() -> None:
    if not _couchdb_ready():
        pytest.skip("CouchDB not available")

    db_name = f"test_articles_validation_{uuid.uuid4().hex}"
    if not _ensure_test_db(db_name):
        pytest.skip("CouchDB user lacks permission to create databases")

    ensure_design_doc(
        db_name,
        "validation",
        views={},
        validate_doc_update=ARTICLE_VALIDATE_DOC.strip(),
    )

    base_url = f"{get_couchdb_uri()}{db_name}"
    valid_article = {
        "feed_url": "https://example.com/rss",
        "title": "Example article",
        "link": "https://example.com/article",
        "published": "2024-01-01T00:00:00Z",
        "language": "en",
    }

    try:
        response = requests.post(base_url, json=valid_article, timeout=5)
        assert response.status_code in (200, 201)

        invalid_article = dict(valid_article)
        invalid_article.pop("language")
        response = requests.post(base_url, json=invalid_article, timeout=5)
        assert response.status_code == 403
    finally:
        _delete_db(db_name)


@pytest.mark.integration
def test_feed_validate_doc_update() -> None:
    if not _couchdb_ready():
        pytest.skip("CouchDB not available")

    db_name = f"test_feeds_validation_{uuid.uuid4().hex}"
    if not _ensure_test_db(db_name):
        pytest.skip("CouchDB user lacks permission to create databases")

    ensure_design_doc(
        db_name,
        "validation",
        views={},
        validate_doc_update=FEED_VALIDATE_DOC.strip(),
    )

    base_url = f"{get_couchdb_uri()}{db_name}"
    valid_feed = {
        "url": "https://example.com/rss",
        "original_url": "https://example.com/rss",
        "category": "general",
        "added_at": "2024-01-01T00:00:00Z",
        "title": "Example feed",
    }

    try:
        response = requests.post(base_url, json=valid_feed, timeout=5)
        assert response.status_code in (200, 201)

        invalid_feed = dict(valid_feed)
        invalid_feed["added_at"] = "2024-01-01"
        response = requests.post(base_url, json=invalid_feed, timeout=5)
        assert response.status_code == 403
    finally:
        _delete_db(db_name)


@pytest.mark.integration
def test_article_stats_view_counts_by_language() -> None:
    if not _couchdb_ready():
        pytest.skip("CouchDB not available")

    db_name = f"test_articles_stats_{uuid.uuid4().hex}"
    if not _ensure_test_db(db_name):
        pytest.skip("CouchDB user lacks permission to create databases")

    ensure_design_doc(
        db_name,
        "stats",
        views=ARTICLE_STATS_VIEWS,
    )

    base_url = f"{get_couchdb_uri()}{db_name}"
    try:
        _insert_docs(
            base_url,
            [
                {"language": "en"},
                {"language": "en"},
                {"language": "fr"},
            ],
        )

        payload = _fetch_view(base_url, "stats", "by_language", {"group": "true"})
        counts = {row["key"]: row["value"] for row in payload.get("rows", [])}
        assert counts["en"] == 2
        assert counts["fr"] == 1
    finally:
        _delete_db(db_name)


@pytest.mark.integration
def test_feed_health_view_counts_by_status() -> None:
    if not _couchdb_ready():
        pytest.skip("CouchDB not available")

    db_name = f"test_feeds_health_{uuid.uuid4().hex}"
    if not _ensure_test_db(db_name):
        pytest.skip("CouchDB user lacks permission to create databases")

    ensure_design_doc(
        db_name,
        "health",
        views=FEED_HEALTH_VIEWS,
    )

    base_url = f"{get_couchdb_uri()}{db_name}"
    try:
        _insert_docs(
            base_url,
            [
                {"last_fetch_error": "timeout"},
                {"last_fetch_error": "rate limited"},
                {},
            ],
        )

        payload = _fetch_view(base_url, "health", "status", {"group": "true"})
        counts = {row["key"]: row["value"] for row in payload.get("rows", [])}
        assert counts["error"] == 2
        assert counts["success"] == 1
    finally:
        _delete_db(db_name)
