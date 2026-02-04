import pytest
import requests
import os
import uuid
import time

# Configuration
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8088")
API_USERNAME = os.environ.get("API_USERNAME", "admin")
API_PASSWORD = os.environ.get("API_PASSWORD", "changeme")

# Track last bulk import call time to manage rate limiting
_rate_limit_window_start = 0
_bulk_call_count = 0

def wait_for_rate_limit():
    """Helper to wait for rate limit before making bulk API calls (5 per minute)"""
    global _rate_limit_window_start, _bulk_call_count
    current_time = time.time()
    
    # If this is the first call or window has expired, start new window
    if _rate_limit_window_start == 0 or (current_time - _rate_limit_window_start) >= 60:
        _rate_limit_window_start = current_time
        _bulk_call_count = 0
    
    # If we've already made 5 calls in this window, wait for window to expire
    if _bulk_call_count >= 5:
        elapsed = current_time - _rate_limit_window_start
        wait_time = 60 - elapsed + 1  # Add 1 second buffer
        if wait_time > 0:
            time.sleep(wait_time)
        # Reset window
        _rate_limit_window_start = time.time()
        _bulk_call_count = 0
    
    # Increment counter for this call
    _bulk_call_count += 1

@pytest.fixture
def auth_headers():
    return {} # Basic auth is handled by requests.auth.HTTPBasicAuth

@pytest.fixture
def wait_for_bulk_rate_limit():
    """Fixture to ensure we don't hit rate limits on bulk import endpoint (5 per minute)"""
    wait_for_rate_limit()
    yield

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

def test_bulk_import_successful(wait_for_bulk_rate_limit):
    """Test successful import of multiple feeds"""
    url = f"{BASE_URL}/api/feeds/bulk"
    unique_id = uuid.uuid4()
    urls = [
        f"https://example.com/feed1-{unique_id}",
        f"https://example.com/feed2-{unique_id}",
        f"https://example.com/feed3-{unique_id}"
    ]
    data = {"urls": urls}
    
    response = requests.post(url, json=data, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 200
    
    result = response.json()
    assert result["total"] == 3
    assert result["success"] == 3
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert len(result["errors"]) == 0

def test_bulk_import_duplicates(wait_for_bulk_rate_limit):
    """Test that duplicate feeds are properly skipped"""
    url = f"{BASE_URL}/api/feeds/bulk"
    unique_id = uuid.uuid4()
    duplicate_url = f"https://example.com/duplicate-{unique_id}"
    
    # First import
    data = {"urls": [duplicate_url]}
    response = requests.post(url, json=data, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 200
    result = response.json()
    assert result["success"] == 1
    
    # Wait for rate limit before second call
    wait_for_rate_limit()
    
    # Second import with same URL
    data = {"urls": [duplicate_url, f"https://example.com/new-{unique_id}"]}
    response = requests.post(url, json=data, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 200
    
    result = response.json()
    assert result["total"] == 2
    assert result["skipped"] == 1  # Duplicate should be skipped
    assert result["success"] == 1   # New URL should succeed
    assert result["failed"] == 0

def test_bulk_import_invalid_urls(wait_for_bulk_rate_limit):
    """Test that invalid URLs are properly reported as errors"""
    url = f"{BASE_URL}/api/feeds/bulk"
    unique_id = uuid.uuid4()
    data = {
        "urls": [
            "not-a-url",
            "ftp://invalid-scheme.com/feed",
            f"https://example.com/valid-{unique_id}",
            "javascript:alert('xss')"
        ]
    }
    
    response = requests.post(url, json=data, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 200
    
    result = response.json()
    assert result["total"] == 4
    assert result["success"] == 1  # Only the valid HTTPS URL
    assert result["failed"] == 3   # Three invalid URLs
    assert len(result["errors"]) == 3
    
    # Verify error messages contain URL validation info
    for error in result["errors"]:
        assert "url" in error
        assert "error" in error
        assert "Invalid URL" in error["error"]

def test_bulk_import_dos_protection(wait_for_bulk_rate_limit):
    """Test that bulk import rejects too many URLs (DoS protection)"""
    url = f"{BASE_URL}/api/feeds/bulk"
    unique_id = uuid.uuid4()
    # Create 51 URLs (exceeds MAX_BULK_IMPORT_SIZE of 50)
    urls = [f"https://example.com/feed{i}-{unique_id}" for i in range(51)]
    data = {"urls": urls}
    
    response = requests.post(url, json=data, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 400
    assert "Too many URLs" in response.text or "Maximum" in response.text

def test_bulk_import_empty_request(wait_for_bulk_rate_limit):
    """Test that empty or missing URLs array is rejected"""
    url = f"{BASE_URL}/api/feeds/bulk"
    
    # Missing urls field
    response = requests.post(url, json={}, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 400
    
    wait_for_rate_limit()
    
    # Empty urls array
    response = requests.post(url, json={"urls": []}, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 400
    
    wait_for_rate_limit()
    
    # Non-array urls field
    response = requests.post(url, json={"urls": "not-an-array"}, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 400

def test_bulk_import_mixed_results(wait_for_bulk_rate_limit):
    """Test bulk import with a mix of valid, invalid, and duplicate URLs"""
    url = f"{BASE_URL}/api/feeds/bulk"
    unique_id = uuid.uuid4()
    
    # First create one feed to test duplicate detection
    valid_url = f"https://example.com/existing-{unique_id}"
    requests.post(url, json={"urls": [valid_url]}, auth=(API_USERNAME, API_PASSWORD))
    
    wait_for_rate_limit()
    
    # Now try bulk import with mixed results
    data = {
        "urls": [
            valid_url,  # Duplicate - should be skipped
            f"https://example.com/new1-{unique_id}",  # Valid
            "invalid-url",  # Invalid - should fail
            f"https://example.com/new2-{unique_id}",  # Valid
            "ftp://invalid-scheme.com"  # Invalid - should fail
        ]
    }
    
    response = requests.post(url, json=data, auth=(API_USERNAME, API_PASSWORD))
    assert response.status_code == 200
    
    result = response.json()
    assert result["total"] == 5
    assert result["success"] == 2   # Two new valid URLs
    assert result["skipped"] == 1   # One duplicate
    assert result["failed"] == 2    # Two invalid URLs
    assert len(result["errors"]) == 2
