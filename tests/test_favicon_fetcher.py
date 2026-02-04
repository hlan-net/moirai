"""
Test the favicon fetcher utility.
"""
import pytest
from tasks.favicon_fetcher import fetch_favicon_url


def test_fetch_favicon_url_basic():
    """Test basic favicon fetching."""
    # Test with example.com - should return a default favicon URL
    result = fetch_favicon_url("https://example.com/rss", timeout=3)
    assert result is not None
    assert isinstance(result, str)
    assert "example.com" in result
    assert "favicon" in result.lower()


def test_fetch_favicon_url_invalid():
    """Test with invalid URL."""
    result = fetch_favicon_url("not-a-valid-url", timeout=1)
    assert result == ""


def test_fetch_favicon_url_timeout():
    """Test that timeout is respected."""
    # This should return a default favicon URL even if the server doesn't respond
    result = fetch_favicon_url("https://httpstat.us/200?sleep=10000", timeout=1)
    # Should return a URL or empty string, but not hang
    assert isinstance(result, str)
