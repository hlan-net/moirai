"""
Route-level tests for /api/agents endpoints.

Covers: auth enforcement, userspace UUID validation, ownership checks,
RBAC (admin vs regular user), cross-userspace access denial, payload
sanitization, and basic CRUD happy-paths.
"""

import os
import secrets
import uuid
from typing import Any
from unittest.mock import patch

import pytest

os.environ.setdefault(
    "JWT_SECRET_KEY", "super_secret_test_key_that_is_at_least_32_chars_long"
)
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password_123")

from main import app  # noqa: E402 – env vars must be set first


# ---------------------------------------------------------------------------
# Minimal in-memory DB fixture
# ---------------------------------------------------------------------------

class AgentMockDB:
    """Minimal mock backing store for agent_configs and users."""

    def __init__(self):
        self.users: dict[str, dict] = {}
        self.agent_configs: dict[str, dict] = {}

    # --- user helpers -------------------------------------------------------
    def get_user_by_email(self, email: str) -> dict | None:
        for uid, user in self.users.items():
            if user.get("email") == email:
                return {**user, "_id": uid}
        return None

    def create_user(self, user_doc: dict) -> tuple[bool, str]:
        email: str = user_doc.get("email") or ""
        if self.get_user_by_email(email):
            return False, "User already exists"
        uid = str(uuid.uuid4())
        user_doc["_id"] = uid
        self.users[uid] = user_doc
        return True, uid

    # --- generic DB helpers -------------------------------------------------
    def fetch_from_couchdb(self, db_name: str, doc_id: str | None = None) -> Any:
        if db_name == "users":
            if doc_id:
                u = self.users.get(doc_id)
                return {**u} if u else None
            return list(self.users.values())
        if db_name == "agent_configs":
            if doc_id:
                doc = self.agent_configs.get(doc_id)
                return {**doc} if doc else None
            return list(self.agent_configs.values())
        if db_name == "config" and doc_id == "main":
            return {"allow_public_read": False}
        if doc_id is None:
            return []
        return None

    def update_couchdb_doc(self, db_name: str, doc_id: str, doc: dict) -> bool:
        if db_name == "agent_configs":
            doc["_rev"] = doc.get("_rev", "1-initial")
            self.agent_configs[doc_id] = {**doc}
            return True
        if db_name == "users":
            if doc_id in self.users:
                self.users[doc_id] = doc
                return True
        if db_name == "config":
            return True
        return False

    def delete_from_couchdb(self, db_name: str, doc_id: str, rev: str) -> bool:
        if db_name == "agent_configs" and doc_id in self.agent_configs:
            del self.agent_configs[doc_id]
            return True
        return False

    def query_couchdb(
        self, db_name: str, selector: dict, **kwargs: Any
    ) -> list[dict]:
        if db_name == "users" and "email" in selector:
            u = self.get_user_by_email(selector["email"])
            return [u] if u else []
        if db_name == "agent_configs":
            # Handle $and / $or selectors used by list_agents
            results = list(self.agent_configs.values())
            return results
        return []

    def store_to_couchdb(self, db_name: str, doc: dict) -> Any:
        if db_name == "users":
            ok, uid = self.create_user(doc)
            return {"id": uid} if ok else None
        return None


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db():
    return AgentMockDB()


def _make_patches(db_instance: AgentMockDB) -> list:
    return [
        patch("api.db.get_user_by_email", side_effect=db_instance.get_user_by_email),
        patch("api.db.create_user", side_effect=db_instance.create_user),
        patch("api.db.fetch_from_couchdb", side_effect=db_instance.fetch_from_couchdb),
        patch("api.db.update_couchdb_doc", side_effect=db_instance.update_couchdb_doc),
        patch("api.db.delete_from_couchdb", side_effect=db_instance.delete_from_couchdb),
        patch("api.db.query_couchdb", side_effect=db_instance.query_couchdb),
        patch("api.db.store_to_couchdb", side_effect=db_instance.store_to_couchdb),
        patch("api.auth.get_user_by_email", side_effect=db_instance.get_user_by_email),
        patch("api.auth.create_user", side_effect=db_instance.create_user),
        patch("api.auth.fetch_from_couchdb", side_effect=db_instance.fetch_from_couchdb),
        patch("api.auth.update_couchdb_doc", side_effect=db_instance.update_couchdb_doc),
        patch("api.routes.fetch_from_couchdb", side_effect=db_instance.fetch_from_couchdb),
        patch("api.routes.update_couchdb_doc", side_effect=db_instance.update_couchdb_doc),
        patch("api.routes.query_couchdb", side_effect=db_instance.query_couchdb),
        patch("api.agent_routes.fetch_from_couchdb", side_effect=db_instance.fetch_from_couchdb),
        patch("api.agent_routes.update_couchdb_doc", side_effect=db_instance.update_couchdb_doc),
        patch("api.agent_routes.delete_from_couchdb", side_effect=db_instance.delete_from_couchdb),
        patch("api.agent_routes.query_couchdb", side_effect=db_instance.query_couchdb),
        patch("tasks.init.init_db"),
    ]


@pytest.fixture(scope="module")
def client(db):
    patches = _make_patches(db)
    started = [p.start() for p in patches]
    flask_client = app.test_client()
    yield flask_client
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_USERSPACE = str(uuid.uuid4())
VALID_OWNER_ID = str(uuid.uuid4())
OTHER_USERSPACE = str(uuid.uuid4())

_USER_EMAIL = f"agent_route_user_{secrets.token_hex(4)}@example.com"
_USER_PASSWORD = "TestPassword123!"
_ADMIN_EMAIL = f"agent_route_admin_{secrets.token_hex(4)}@example.com"
_ADMIN_PASSWORD = "AdminPassword123!"

# Tokens cached across tests
_tokens: dict[str, str] = {}
_user_ids: dict[str, str] = {}


def _register_and_login(client, db_instance: AgentMockDB, email: str, password: str, make_admin: bool = False) -> tuple[str, str]:
    """Register a user, optionally promote to admin, then return a JWT."""
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.get_data(as_text=True)
    uid = resp.get_json()["user_id"]
    if make_admin:
        user_doc = db_instance.fetch_from_couchdb("users", uid)
        user_doc["role"] = "admin"
        db_instance.update_couchdb_doc("users", uid, user_doc)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.get_json()["access_token"], uid


def _agent_payload(
    userspace: str | None = None,
    owner_user_id: str | None = None,
    trigger_type: str = "on_new_article",
    logic_module: str = "tasks.agent_logic.create_event_from_articles",
) -> dict:
    return {
        "name": "Test Agent",
        "userspace": userspace or VALID_USERSPACE,
        "owner_user_id": owner_user_id,  # may be None; overridden by route
        "trigger_type": trigger_type,
        "target_db": "articles",
        "logic_module": logic_module,
    }


# ---------------------------------------------------------------------------
# Setup tokens (module-scoped, run once via a test)
# ---------------------------------------------------------------------------

def test_00_setup_tokens(client, db):
    """Bootstrap user and admin tokens for subsequent tests."""
    token, uid = _register_and_login(client, db, _USER_EMAIL, _USER_PASSWORD)
    _tokens["user"] = token
    _user_ids["user"] = uid

    admin_token, admin_uid = _register_and_login(
        client, db, _ADMIN_EMAIL, _ADMIN_PASSWORD, make_admin=True
    )
    _tokens["admin"] = admin_token
    _user_ids["admin"] = admin_uid


# ---------------------------------------------------------------------------
# Authentication enforcement
# ---------------------------------------------------------------------------

def test_list_agents_requires_auth(client):
    """GET /api/agents without a token must return 401."""
    resp = client.get(f"/api/agents?userspace={VALID_USERSPACE}")
    assert resp.status_code == 401


def test_create_agent_requires_auth(client):
    """POST /api/agents without a token must return 401."""
    resp = client.post("/api/agents", json=_agent_payload())
    assert resp.status_code == 401


def test_get_agent_requires_auth(client):
    """GET /api/agents/<id> without a token must return 401."""
    resp = client.get(f"/api/agents/nonexistent?userspace={VALID_USERSPACE}")
    assert resp.status_code == 401


def test_update_agent_requires_auth(client):
    """PUT /api/agents/<id> without a token must return 401."""
    resp = client.put("/api/agents/nonexistent", json={"userspace": VALID_USERSPACE})
    assert resp.status_code == 401


def test_delete_agent_requires_auth(client):
    """DELETE /api/agents/<id> without a token must return 401."""
    resp = client.delete(f"/api/agents/nonexistent?userspace={VALID_USERSPACE}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Userspace UUID validation
# ---------------------------------------------------------------------------

def test_list_agents_missing_userspace(client):
    """GET /api/agents without userspace param must return 400."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    resp = client.get("/api/agents", headers=headers)
    assert resp.status_code == 400


def test_list_agents_invalid_userspace_format(client):
    """GET /api/agents with a non-UUID userspace must return 400."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    resp = client.get("/api/agents?userspace=not-a-uuid", headers=headers)
    assert resp.status_code == 400


def test_create_agent_missing_userspace(client):
    """POST /api/agents with no userspace field must return 400."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    payload = _agent_payload()
    del payload["userspace"]
    resp = client.post("/api/agents", json=payload, headers=headers)
    assert resp.status_code == 400


def test_create_agent_invalid_userspace_format(client):
    """POST /api/agents with a non-UUID userspace must return 400."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    payload = _agent_payload(userspace="not-a-valid-uuid")
    resp = client.post("/api/agents", json=payload, headers=headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Happy-path CRUD
# ---------------------------------------------------------------------------

_created_agent_id: dict[str, str] = {}


def test_create_agent_success(client):
    """POST /api/agents with valid payload must return 201 and the new doc."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    payload = _agent_payload(owner_user_id=_user_ids["user"])
    resp = client.post("/api/agents", json=payload, headers=headers)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["name"] == "Test Agent"
    assert data["userspace"] == VALID_USERSPACE
    _created_agent_id["id"] = data["_id"]


def test_get_agent_success(client):
    """GET /api/agents/<id> for an owned agent must return 200."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    agent_id = _created_agent_id["id"]
    resp = client.get(
        f"/api/agents/{agent_id}?userspace={VALID_USERSPACE}", headers=headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["_id"] == agent_id


def test_update_agent_success(client):
    """PUT /api/agents/<id> for an owned agent must return 200 with updated data."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    agent_id = _created_agent_id["id"]
    resp = client.put(
        f"/api/agents/{agent_id}",
        json={"userspace": VALID_USERSPACE, "name": "Updated Agent"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "Updated Agent"


def test_list_agents_returns_created_agent(client):
    """GET /api/agents must include the previously created agent."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    resp = client.get(f"/api/agents?userspace={VALID_USERSPACE}", headers=headers)
    assert resp.status_code == 200
    ids = [a["_id"] for a in resp.get_json()]
    assert _created_agent_id["id"] in ids


def test_delete_agent_success(client, db):
    """DELETE /api/agents/<id> for an owned agent must return 200."""
    # Create a fresh agent to delete
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    payload = _agent_payload(owner_user_id=_user_ids["user"])
    create_resp = client.post("/api/agents", json=payload, headers=headers)
    assert create_resp.status_code == 201
    new_id = create_resp.get_json()["_id"]

    resp = client.delete(
        f"/api/agents/{new_id}?userspace={VALID_USERSPACE}", headers=headers
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "deleted"
    assert data["agent_id"] == new_id


# ---------------------------------------------------------------------------
# Ownership and cross-userspace access denial
# ---------------------------------------------------------------------------

def test_get_agent_wrong_userspace_returns_404(client):
    """GET /api/agents/<id> with a different userspace must return 404."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    agent_id = _created_agent_id["id"]
    resp = client.get(
        f"/api/agents/{agent_id}?userspace={OTHER_USERSPACE}", headers=headers
    )
    assert resp.status_code == 404


def test_get_nonexistent_agent_returns_404(client):
    """GET /api/agents/<id> for a nonexistent ID must return 404."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    resp = client.get(
        f"/api/agents/{uuid.uuid4()}?userspace={VALID_USERSPACE}", headers=headers
    )
    assert resp.status_code == 404


def test_delete_agent_wrong_userspace_returns_404(client):
    """DELETE /api/agents/<id> with a different userspace must return 404."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    agent_id = _created_agent_id["id"]
    resp = client.delete(
        f"/api/agents/{agent_id}?userspace={OTHER_USERSPACE}", headers=headers
    )
    assert resp.status_code == 404


def test_admin_cannot_set_other_owner_as_non_admin(client):
    """Non-admin user setting owner_user_id to another user's ID must return 403."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    other_user_id = str(uuid.uuid4())
    payload = _agent_payload(owner_user_id=other_user_id)
    resp = client.post("/api/agents", json=payload, headers=headers)
    assert resp.status_code == 403


def test_admin_can_create_agent_for_any_owner(client):
    """Admin user can create an agent with an arbitrary owner_user_id."""
    headers = {"Authorization": f"Bearer {_tokens['admin']}"}
    other_owner = str(uuid.uuid4())
    payload = _agent_payload(owner_user_id=other_owner)
    resp = client.post("/api/agents", json=payload, headers=headers)
    assert resp.status_code == 201
    assert resp.get_json()["owner_user_id"] == other_owner


# ---------------------------------------------------------------------------
# Payload validation
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason=(
        "logic_module allowlist not yet enforced at write time on this branch. "
        "Will pass once improvement/logic-module-allowlist is merged."
    ),
    strict=True,
)
def test_create_agent_invalid_logic_module(client):
    """POST /api/agents with an unknown logic_module must return 400."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    payload = _agent_payload(
        owner_user_id=_user_ids["user"],
        logic_module="tasks.malicious.pwn_everything",
    )
    resp = client.post("/api/agents", json=payload, headers=headers)
    assert resp.status_code == 400, (
        "Expected 400 – logic_module allowlist not yet enforced at write time. "
        "Merge improvement/logic-module-allowlist first."
    )


def test_create_agent_invalid_trigger_type(client):
    """POST /api/agents with an unrecognised trigger_type must return 400."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    payload = _agent_payload(
        owner_user_id=_user_ids["user"],
        trigger_type="whenever_i_feel_like_it",
    )
    resp = client.post("/api/agents", json=payload, headers=headers)
    assert resp.status_code == 400


def test_create_agent_xss_name_is_sanitized(client, db):
    """POST /api/agents with an XSS payload in name must strip HTML tags."""
    headers = {"Authorization": f"Bearer {_tokens['user']}"}
    # bleach.clean strips tags but preserves text content, so the name will
    # become "alert('xss')Evil Agent" (tags removed, text retained)
    xss_name = "<script>alert('xss')</script>Evil Agent"
    payload = _agent_payload(owner_user_id=_user_ids["user"])
    payload["name"] = xss_name
    resp = client.post("/api/agents", json=payload, headers=headers)
    assert resp.status_code == 201
    stored_name = resp.get_json()["name"]
    # Script tags must be gone
    assert "<script>" not in stored_name
    assert "</script>" not in stored_name
