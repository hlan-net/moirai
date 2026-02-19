import requests
import os
import pytest
import secrets

# Configuration - follow same pattern as test_security_api.py
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8088")
# Generate random credentials per test run if not provided via environment
# This avoids hardcoded credentials flagged as security hotspots by SonarQube
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME") or f"test_user_{secrets.token_hex(8)}"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(32)


@pytest.mark.integration
def test_stats_endpoint_auth():
    """Verify that the /stats endpoint requires authentication."""
    res = requests.get(f"{BASE_URL}/api/stats")
    assert res.status_code == 401


@pytest.mark.integration
def test_stats_endpoint_data():
    """Verify the structure of the /stats response."""
    res = requests.get(f"{BASE_URL}/api/stats", auth=(ADMIN_USERNAME, ADMIN_PASSWORD))
    assert res.status_code == 200

    data = res.json()
    assert "articles" in data
    assert "by_language" in data["articles"]
    assert "total" in data["articles"]

    assert "feeds" in data
    assert "health" in data["feeds"]
    assert "total" in data["feeds"]


if __name__ == "__main__":
    # Manual test run
    print(f"Testing Stats API at {BASE_URL}/api/stats...")
    try:
    res = requests.get(f"{BASE_URL}/api/stats", auth=(ADMIN_USERNAME, ADMIN_PASSWORD))
        if res.status_code == 200:
            print("SUCCESS: Stats API returned data:")
            import json

            print(json.dumps(res.json(), indent=2))
        else:
            print(f"FAILED: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error connecting to API: {e}")
