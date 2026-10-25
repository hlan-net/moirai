"""Route tests for the admin-editable model catalog (/api/llm/catalog)."""

import json
import os

os.environ.setdefault(
    "JWT_SECRET_KEY", "super_secret_test_key_that_is_at_least_32_chars_long"
)
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password_123")

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

from api.auth import create_access_token  # noqa: E402
from api.llm import catalog as cat  # noqa: E402
from main import app  # noqa: E402

VALID = {
    "catalog": {
        "npu-qwen": {
            "provider": "ollama",
            "endpoint": "http://ergo:8000/v1",
            "model": "qwen3:1.7b",
            "languages": ["EN"],
        },
        "aisa": {"provider": "aisa", "capabilities": ["chat", "json", "tools"]},
    },
    "purposes": {
        "annotation": ["npu-qwen", "aisa"],
        "chat": ["aisa"],
        "social_export": [],
    },
}


class FakeConfigDB:
    def __init__(self):
        self.doc = None
        self.rev = 0

    def fetch(self, db_name, doc_id=None):
        assert (db_name, doc_id) == (cat.CATALOG_DB, cat.CATALOG_DOC_ID)
        return dict(self.doc) if self.doc else None

    def update(self, db_name, doc_id, doc):
        if self.doc and doc.get("_rev") != self.doc["_rev"]:
            return False
        self.rev += 1
        self.doc = {**doc, "_id": doc_id, "_rev": f"{self.rev}-x"}
        return True

    def delete(self, db_name, doc_id, rev):
        assert rev == self.doc["_rev"]
        self.doc = None
        return True


@pytest.fixture
def db(monkeypatch):
    fake = FakeConfigDB()
    monkeypatch.setattr(cat, "_fetch_catalog_doc", lambda: fake.doc)
    with (
        patch("api.routes.fetch_from_couchdb", side_effect=fake.fetch),
        patch("api.routes.update_couchdb_doc", side_effect=fake.update),
        patch("api.routes.delete_from_couchdb", side_effect=fake.delete),
    ):
        yield fake


@pytest.fixture
def client():
    return app.test_client()


def _headers(role: str = "admin") -> dict:
    token = create_access_token(
        {"sub": "u1", "email": "lari@example.com", "role": role}
    )
    return {"Authorization": f"Bearer {token}"}


def test_requires_admin(client, db):
    assert client.get("/api/llm/catalog").status_code == 401
    assert client.get("/api/llm/catalog", headers=_headers("user")).status_code == 403
    res = client.put("/api/llm/catalog", json=VALID, headers=_headers("user"))
    assert res.status_code == 403
    assert db.doc is None


def test_get_without_catalog(client, db, monkeypatch):
    monkeypatch.delenv(cat.CATALOG_FILE_ENV, raising=False)
    data = client.get("/api/llm/catalog", headers=_headers()).get_json()
    assert data["source"] == "none"
    assert data["catalog"] == {} and data["file"] is None
    assert {p["id"]: p["needs"] for p in data["purpose_info"]}["annotation"] == "json"
    assert "aisa" in data["providers"] and "embedding" in data["capabilities"]


def test_get_shows_file_until_saved(client, db, tmp_path, monkeypatch):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"catalog": {"x": {"provider": "aisa"}}}))
    monkeypatch.setenv(cat.CATALOG_FILE_ENV, str(path))
    data = client.get("/api/llm/catalog", headers=_headers()).get_json()
    assert data["source"] == "file"
    assert data["catalog"] == {"x": {"provider": "aisa"}}


def test_put_stores_normalised_document_and_takes_effect(client, db, monkeypatch):
    monkeypatch.setenv("AISA_BASE_URL", "http://aisa/v1")
    monkeypatch.setenv("AISA_MODEL", "qwen3:8b")
    res = client.put("/api/llm/catalog", json=VALID, headers=_headers())
    assert res.status_code == 200, res.get_json()
    data = res.get_json()
    assert data["source"] == "database"
    assert data["updated_by"] == "lari@example.com"
    assert data["skipped"] == []
    stored = db.doc
    assert stored["catalog"]["npu-qwen"] == {
        "provider": "ollama",
        "endpoint": "http://ergo:8000/v1",
        "model": "qwen3:1.7b",
        "languages": ["en"],
    }
    assert "social_export" not in stored["purposes"]
    # The active catalog follows the stored document immediately.
    assert [e.name for e in cat.resolve_models("annotation", "en")] == [
        "npu-qwen",
        "aisa",
    ]
    # A second save updates the same document (its _rev is carried over).
    edited = {**VALID, "purposes": {"annotation": ["aisa"]}}
    assert (
        client.put("/api/llm/catalog", json=edited, headers=_headers()).status_code
        == 200
    )
    assert db.rev == 2
    assert [e.name for e in cat.resolve_models("annotation", "en")] == ["aisa"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"catalog": {"a": {"provider": "nope", "model": "m"}}}, "provider must be"),
        ({"catalog": {"a": {"provider": "openai"}}}, "model is required"),
        (
            {"catalog": {"a": {"provider": "ollama", "model": "m"}}},
            "endpoint is required",
        ),
        (
            {
                "catalog": {
                    "a": {"provider": "ollama", "endpoint": "ftp://x", "model": "m"}
                }
            },
            "http(s) URL",
        ),
        (
            {
                "catalog": {
                    "a": {
                        "provider": "openai",
                        "model": "m",
                        "apiKeyEnv": "JWT_SECRET_KEY",
                    }
                }
            },
            "_API_KEY",
        ),
        ({"catalog": {"bad name": {"provider": "aisa"}}}, "invalid entry names"),
        ({"catalog": {"a": {"provider": "aisa", "apiKey": "sk-1"}}}, "Extra inputs"),
        ({"purposes": {"annotation": ["missing"]}}, "unknown entry"),
        ({"purposes": {"nonsense": []}}, "unknown purpose"),
        (
            {
                "catalog": {"e": {"provider": "aisa", "capabilities": ["embedding"]}},
                "purposes": {"chat": ["e"]},
            },
            "needs 'chat'",
        ),
    ],
)
def test_put_rejects_invalid_catalog(client, db, change, message):
    body = {"catalog": {}, "purposes": {}, **change}
    res = client.put("/api/llm/catalog", json=body, headers=_headers())
    assert res.status_code == 400
    assert any(message in d for d in res.get_json()["details"]), res.get_json()
    assert db.doc is None


def test_aisa_entry_without_any_model_is_reported_skipped(client, db, monkeypatch):
    for var in ("AISA_BASE_URL", "AISA_MODEL", "OPENAI_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    res = client.put("/api/llm/catalog", json=VALID, headers=_headers())
    assert res.get_json()["skipped"] == ["aisa"]


def test_delete_reverts_to_file(client, db, monkeypatch):
    monkeypatch.delenv(cat.CATALOG_FILE_ENV, raising=False)
    client.put("/api/llm/catalog", json=VALID, headers=_headers())
    data = client.delete("/api/llm/catalog", headers=_headers()).get_json()
    assert data["source"] == "none"
    assert db.doc is None
    assert cat.load_catalog() is None
