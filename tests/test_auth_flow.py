import unittest
import requests
import os
import time
import secrets
from urllib.parse import quote

# Configuration
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8088")

# --- Standalone DB Helpers to avoid importing app modules with missing dependencies ---
def get_couchdb_uri():
    couchdb_uri = os.environ.get("COUCHDB_URI", "http://localhost:5984/").rstrip("/")
    user = os.environ.get("COUCHDB_USER")
    password = os.environ.get("COUCHDB_PASSWORD")
    
    if user and password and "@" not in couchdb_uri:
        if "://" in couchdb_uri:
            scheme, host = couchdb_uri.split("://", 1)
        else:
            scheme, host = "http", couchdb_uri
        couchdb_uri = f"{scheme}://{quote(user)}:{quote(password)}@{host}"
    
    if not couchdb_uri.endswith("/"):
        couchdb_uri += "/"
    return couchdb_uri

COUCHDB_URI = get_couchdb_uri()

def fetch_from_couchdb_standalone(db_name, doc_id):
    """Fetch doc directly from CouchDB."""
    try:
        url = f"{COUCHDB_URI}{db_name}/{doc_id}"
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"DB Error: {e}")
        return None

def update_couchdb_doc_standalone(db_name, doc_id, doc):
    """Update doc directly in CouchDB."""
    try:
        url = f"{COUCHDB_URI}{db_name}/{doc_id}"
        resp = requests.put(url, json=doc)
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"DB Update Error: {e}")
        return False
# -----------------------------------------------------------------------------------

class TestAuthFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unique_suffix = secrets.token_hex(4)
        cls.user_credentials = {
            "email": f"test_user_{cls.unique_suffix}@example.com",
            "password": "SecurePassword123!"
        }
        cls.admin_credentials = {
            "email": f"admin_user_{cls.unique_suffix}@example.com",
            "password": "SecureAdminPassword123!"
        }

    def test_01_register_user(self):
        """Test user registration endpoint"""
        url = f"{BASE_URL}/api/auth/register"
        response = requests.post(url, json=self.user_credentials)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("user_id", data)
        self.assertEqual(data["message"], "User registered successfully")
        self.__class__.user_id = data["user_id"]

    def test_02_login_user(self):
        """Test user login endpoint"""
        url = f"{BASE_URL}/api/auth/login"
        response = requests.post(url, json=self.user_credentials)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["email"], self.user_credentials["email"])
        self.assertEqual(data["role"], "user")
        self.__class__.user_token = data["access_token"]

    def test_03_register_and_promote_admin(self):
        """Register a user and promote to admin via DB manipulation (for testing RBAC)"""
        # 1. Register
        url = f"{BASE_URL}/api/auth/register"
        response = requests.post(url, json=self.admin_credentials)
        self.assertEqual(response.status_code, 201)
        user_id = response.json().get("user_id")
        
        # 2. Promote to Admin (Direct DB manipulation)
        time.sleep(1)
        user_doc = fetch_from_couchdb_standalone("users", user_id)
        self.assertIsNotNone(user_doc, "Failed to fetch user doc for promotion")
        
        user_doc["role"] = "admin"
        success = update_couchdb_doc_standalone("users", user_id, user_doc)
        self.assertTrue(success, "Failed to update user role in DB")
        
        # 3. Login to get Admin Token
        login_url = f"{BASE_URL}/api/auth/login"
        response = requests.post(login_url, json=self.admin_credentials)
        self.assertEqual(response.status_code, 200)
        self.__class__.admin_token = response.json().get("access_token")

    def test_04_protected_route_access(self):
        """Test access to protected routes with and without token"""
        # Access protected route (e.g. /api/auth/me)
        url = f"{BASE_URL}/api/auth/me"
        headers = {"Authorization": f"Bearer {self.__class__.user_token}"}
        
        # With token
        response = requests.get(url, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], self.user_credentials["email"])
        
        # Without token
        response = requests.get(url)
        self.assertEqual(response.status_code, 401)

    def test_05_admin_route_access(self):
        """Test RBAC on admin routes"""
        url = f"{BASE_URL}/api/config"
        user_headers = {"Authorization": f"Bearer {self.__class__.user_token}"}
        admin_headers = {"Authorization": f"Bearer {self.__class__.admin_token}"}
        
        # User should fail to PUT config
        response = requests.put(url, headers=user_headers, json={"allow_public_read": True})
        self.assertEqual(response.status_code, 403)
        
        # Admin should succeed
        response = requests.put(url, headers=admin_headers, json={"allow_public_read": True})
        self.assertEqual(response.status_code, 200)

    def test_06_public_read_access_control(self):
        """verify allow_public_read setting controls access"""
        admin_headers = {"Authorization": f"Bearer {self.__class__.admin_token}"}
        
        # 1. Disable Public Read
        requests.put(f"{BASE_URL}/api/config", headers=admin_headers, json={"allow_public_read": False})
        
        # 2. Access Public Route without token -> 401
        resp = requests.get(f"{BASE_URL}/api/articles")
        self.assertEqual(resp.status_code, 401)
        
        # 3. Enable Public Read
        requests.put(f"{BASE_URL}/api/config", headers=admin_headers, json={"allow_public_read": True})
        
        # 4. Access Public Route without token -> 200
        resp = requests.get(f"{BASE_URL}/api/articles")
        self.assertEqual(resp.status_code, 200)

if __name__ == "__main__":
    unittest.main()
