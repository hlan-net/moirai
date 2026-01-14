import pytest
import requests
import os
import uuid

# Configuration
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8088")
API_USERNAME = os.environ.get("API_USERNAME", "admin")
API_PASSWORD = os.environ.get("API_PASSWORD", "changeme")

@pytest.fixture
def auth_headers():
    return {} # Basic auth is handled by requests.auth.HTTPBasicAuth

def test_feed_url_validation_http():
    """Test that creating a feed with invalid URL scheme fails"""
    url = f"{BASE_URL}/api/feeds"
    data = {
        "url": "ftp://example.com/feed",
        "title": "Invalid Scheme",
        "category": "test"
    }
    response = requests.post(url, json=data, auth=(API_USERNAME, API_PASSWORD))
    # Should fail with 400 Bad Request
    assert response.status_code == 400
    # Check for validation error (Pydantic or custom)
    assert "validation error" in response.text.lower() or "only http/https" in response.text.lower()

def test_feed_url_validation_valid():
    """Test that creating a feed with valid URL scheme succeeds"""
    url = f"{BASE_URL}/api/feeds"
    # Using a fake but valid URL hash to avoid collision with real feeds
    unique_url = f"https://example.com/feed-{uuid.uuid4()}"
    data = {
        "url": unique_url,
        "title": "Valid Scheme",
        "category": "test"
    }
    response = requests.post(url, json=data, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code in [200, 201]

def test_namespace_validation_invalid_guid():
    """Test that invalid namespace GUID is rejected"""
    url = f"{BASE_URL}/api/events"
    params = {"namespace": "not-a-guid"}
    response = requests.get(url, params=params, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 400
    assert "Invalid namespace GUID format" in response.text

def test_xss_sanitization():
    """Test that HTML tags are stripped from titles"""
    url = f"{BASE_URL}/api/feeds"
    unique_url = f"https://example.com/feed-{uuid.uuid4()}"
    malicious_title = "<script>alert('xss')</script>Safe Title"
    data = {
        "url": unique_url,
        "title": malicious_title,
        "category": "test"
    }
    response = requests.post(url, json=data, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code in [200, 201]
    
    # Fetch back to verify sanitization
    # Note: This depends on how the ID is generated. Assuming URL hash or similar.
    # Alternatively, listing feeds and finding it.
    feeds_response = requests.get(url, auth=(API_USERNAME, API_PASSWORD))
    feeds = feeds_response.json()
    created_feed = next((f for f in feeds if f.get("url") == unique_url), None)
    
    assert created_feed is not None
    assert "<script>" not in created_feed["title"]
    assert "Safe Title" in created_feed["title"]

def test_rate_limiting():
    """Test that rate limits are enforced (smoke test)"""
    # This might fail if run against a fresh instance with high limits, 
    # but we can check headers to see if rate limit info is present.
    url = f"{BASE_URL}/api/config" 
    response = requests.get(url, auth=(API_USERNAME, API_PASSWORD)) # Public endpoint usually
    
    # Flask-Limiter usually adds headers like X-RateLimit-Limit
    # Note: Health endpoint might be exempted or have very high limits.
    # Let's try /api/feeds without auth (if public read) or with auth.
    
    # We will just verify the headers exist on a standard API call
    response = requests.get(f"{BASE_URL}/api/feeds", auth=(API_USERNAME, API_PASSWORD))
    
    # These headers are configurable, but default is usually X-RateLimit-Limit
    # If using memory storage and default config, they should be there.
    # Check for any RateLimit header
    rate_limit_headers = [h for h in response.headers if 'RateLimit' in h]
    if not rate_limit_headers:
        print(f"DEBUG: Headers: {response.headers}")
        pytest.fail("Rate limit headers not found")
    
    assert len(rate_limit_headers) > 0
