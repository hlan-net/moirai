import unittest
import secrets
import logging
import os
import base64
from unittest.mock import patch

# Set environment variables BEFORE importing app.
# Use setdefault to avoid overwriting vars already set by the test runner
# (e.g., integration tests set ADMIN_USERNAME/ADMIN_PASSWORD to specific values).
os.environ.setdefault("JWT_SECRET_KEY", "super_secret_test_key_that_is_at_least_32_chars_long")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password_123")

from main import app

# Disable logging during tests
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("api.db").setLevel(logging.ERROR)


class MockDB:
    def __init__(self):
        self.users = {}
        self.config = {"main": {"allow_public_read": False}}

    def get_user_by_email(self, email):
        for uid, user in self.users.items():
            if user.get("email") == email:
                user_copy = user.copy()
                user_copy["_id"] = uid
                return user_copy
        return None

    def create_user(self, user_doc):
        email = user_doc.get("email")
        if self.get_user_by_email(email):
            return False, "User already exists"

        user_id = secrets.token_hex(8)
        user_doc["_id"] = user_id
        self.users[user_id] = user_doc
        return True, user_id

    def fetch_from_couchdb(self, db_name, doc_id=None):
        if db_name == "users":
            if doc_id:
                user = self.users.get(doc_id)
                return user.copy() if user else None
            return list(self.users.values())
        elif db_name == "config" and doc_id == "main":
            return self.config.get("main")
        # For other DBs like 'articles', return empty list for list calls
        if doc_id is None:
            return []
        return None

    def update_couchdb_doc(self, db_name, doc_id, doc):
        if db_name == "users":
            if doc_id in self.users:
                self.users[doc_id] = doc
                return True
        elif db_name == "config" and doc_id == "main":
            self.config["main"] = doc
            return True
        return False

    def store_to_couchdb(self, db_name, doc):
        # Generic store, mostly used for users in auth flow via create_user
        if db_name == "users":
            return self.create_user(doc)
        return None

    def query_couchdb(
        self, db_name, selector, limit=None, skip=0, sort=None, fields=None
    ):
        # Very basic mock for query
        if db_name == "users" and "email" in selector:
            email = selector["email"]
            user = self.get_user_by_email(email)
            return [user] if user else []
        return []


mock_db = MockDB()


# Mock functions to replace api.db imports
def side_effect_get_user(email):
    return mock_db.get_user_by_email(email)


def side_effect_create_user(user_doc):
    return mock_db.create_user(user_doc)


def side_effect_fetch(db_name, doc_id=None):
    return mock_db.fetch_from_couchdb(db_name, doc_id)


def side_effect_update(db_name, doc_id, doc):
    return mock_db.update_couchdb_doc(db_name, doc_id, doc)


def side_effect_query(db_name, selector, limit=None, skip=0, sort=None, fields=None):
    return mock_db.query_couchdb(db_name, selector, limit, skip, sort, fields)


class TestAuthFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Patch init.init_db to do nothing
        cls.init_patcher = patch("tasks.init.init_db")
        cls.init_patcher.start()

        # Patch api.db functions in both api.db and api.auth/api.routes
        cls.patches = [
            patch("api.db.get_user_by_email", side_effect=side_effect_get_user),
            patch("api.db.create_user", side_effect=side_effect_create_user),
            patch("api.db.fetch_from_couchdb", side_effect=side_effect_fetch),
            patch("api.db.update_couchdb_doc", side_effect=side_effect_update),
            patch("api.db.query_couchdb", side_effect=side_effect_query),
            # Patch where imported
            patch("api.auth.get_user_by_email", side_effect=side_effect_get_user),
            patch("api.auth.create_user", side_effect=side_effect_create_user),
            patch("api.auth.fetch_from_couchdb", side_effect=side_effect_fetch),
            patch("api.auth.update_couchdb_doc", side_effect=side_effect_update),
            patch("api.routes.fetch_from_couchdb", side_effect=side_effect_fetch),
            patch("api.routes.update_couchdb_doc", side_effect=side_effect_update),
            # Note: api.routes imports query_couchdb too
            patch("api.routes.query_couchdb", side_effect=side_effect_query),
        ]

        for p in cls.patches:
            p.start()

        cls.client = app.test_client()
        cls.unique_suffix = secrets.token_hex(4)
        cls.user_credentials = {
            "email": f"test_user_{cls.unique_suffix}@example.com",
            "password": "SecurePassword123!",
        }
        cls.admin_credentials = {
            "email": f"admin_user_{cls.unique_suffix}@example.com",
            "password": "SecureAdminPassword123!",
        }
        cls.admin_basic_credentials = {
            "username": os.environ["ADMIN_USERNAME"],
            "password": os.environ["ADMIN_PASSWORD"],
        }

    @classmethod
    def tearDownClass(cls):
        cls.init_patcher.stop()
        for p in cls.patches:
            p.stop()

    def test_01_register_user(self):
        """Test user registration endpoint"""
        response = self.client.post("/api/auth/register", json=self.user_credentials)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn("user_id", data)
        self.assertEqual(data["message"], "User registered successfully")
        self.__class__.user_id = data["user_id"]

    def test_02_login_user(self):
        """Test user login endpoint"""
        response = self.client.post("/api/auth/login", json=self.user_credentials)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("access_token", data)
        self.assertEqual(data["email"], self.user_credentials["email"])
        self.assertEqual(data["role"], "user")
        self.__class__.user_token = data["access_token"]

    def test_03_register_and_promote_admin(self):
        """Register a user and promote to admin via DB manipulation (for testing RBAC)"""
        # 1. Register
        response = self.client.post("/api/auth/register", json=self.admin_credentials)
        self.assertEqual(response.status_code, 201)
        user_id = response.get_json().get("user_id")

        # 2. Promote to Admin (Direct DB manipulation using mock DB)
        # We access mock_db directly here to simulate 'admin/backend' access
        user_doc = mock_db.fetch_from_couchdb("users", user_id)
        self.assertIsNotNone(user_doc, "Failed to fetch user doc for promotion")

        user_doc["role"] = "admin"
        success = mock_db.update_couchdb_doc("users", user_id, user_doc)
        self.assertTrue(success, "Failed to update user role in DB")

        # 3. Login to get Admin Token
        response = self.client.post("/api/auth/login", json=self.admin_credentials)
        self.assertEqual(response.status_code, 200)
        self.__class__.admin_token = response.get_json().get("access_token")

    def test_04_protected_route_access(self):
        """Test access to protected routes with and without token"""
        # Access protected route (e.g. /api/auth/me)
        headers = {"Authorization": f"Bearer {self.__class__.user_token}"}

        # With token
        response = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["email"], self.user_credentials["email"])

        # Without token
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_05_admin_route_access(self):
        """Test RBAC on admin routes"""
        user_headers = {"Authorization": f"Bearer {self.__class__.user_token}"}
        admin_headers = {"Authorization": f"Bearer {self.__class__.admin_token}"}

        # User should fail to PUT config
        response = self.client.put(
            "/api/config", headers=user_headers, json={"allow_public_read": True}
        )
        self.assertEqual(response.status_code, 403)

        # Admin should succeed
        response = self.client.put(
            "/api/config", headers=admin_headers, json={"allow_public_read": True}
        )
        self.assertEqual(response.status_code, 200)

    def test_06_public_read_access_control(self):
        """verify allow_public_read setting controls access"""
        admin_headers = {"Authorization": f"Bearer {self.__class__.admin_token}"}

        # 1. Disable Public Read
        self.client.put(
            "/api/config", headers=admin_headers, json={"allow_public_read": False}
        )

        # 2. Access Public Route without token -> 401
        resp = self.client.get("/api/articles")
        self.assertEqual(resp.status_code, 401)

        # 3. Enable Public Read
        self.client.put(
            "/api/config", headers=admin_headers, json={"allow_public_read": True}
        )

        # 4. Access Public Route without token -> 200
        resp = self.client.get("/api/articles")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
    def test_00_admin_basic_auth_login(self):
        """Test Basic Auth login for admin user."""
        creds = f"{self.__class__.admin_basic_credentials['username']}:{self.__class__.admin_basic_credentials['password']}"
        auth_header = {
            "Authorization": f"Basic {base64.b64encode(creds.encode()).decode()}"
        }

        response = self.client.get("/api/auth/me", headers=auth_header)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["role"], "admin")
        self.assertEqual(data["email"], "admin@localhost.local")
