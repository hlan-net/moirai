import requests
import os
import pytest

# Use local environment variables or defaults
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8088/api")
USERNAME = os.environ.get("API_USERNAME", "username")
PASSWORD = os.environ.get("API_PASSWORD", "password")

@pytest.mark.integration
def test_stats_endpoint_auth():
    """Verify that the /stats endpoint requires authentication."""
    res = requests.get(f"{API_BASE}/stats")
    assert res.status_code == 401

@pytest.mark.integration
def test_stats_endpoint_data():
    """Verify the structure of the /stats response."""
    res = requests.get(f"{API_BASE}/stats", auth=(USERNAME, PASSWORD))
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
    print(f"Testing Stats API at {API_BASE}...")
    try:
        res = requests.get(f"{API_BASE}/stats", auth=(USERNAME, PASSWORD))
        if res.status_code == 200:
            print("SUCCESS: Stats API returned data:")
            import json
            print(json.dumps(res.json(), indent=2))
        else:
            print(f"FAILED: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error connecting to API: {e}")
