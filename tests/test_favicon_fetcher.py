"""
Test the favicon fetcher utility.
"""

import unittest
from unittest.mock import patch, Mock
from tasks.favicon_fetcher import fetch_favicon_url


class TestFaviconFetcher(unittest.TestCase):
    """Test cases for favicon fetcher with HTTPS enforcement."""

    def test_fetch_favicon_url_https_success(self):
        """Test successful HTTPS favicon fetching."""
        with patch("tasks.favicon_fetcher.requests.head") as mock_head:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "image/x-icon"}
            mock_head.return_value = mock_response

            result = fetch_favicon_url("https://example.com/rss", timeout=3)

            # Should return HTTPS URL
            self.assertEqual(result, "https://example.com/favicon.ico")
            # Should verify SSL
            mock_head.assert_called_once()
            self.assertTrue(mock_head.call_args.kwargs["verify"])

    def test_fetch_favicon_url_enforces_https(self):
        """Test that HTTP feed URLs are upgraded to HTTPS for favicon."""
        with patch("tasks.favicon_fetcher.requests.head") as mock_head:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "image/x-icon"}
            mock_head.return_value = mock_response

            # Feed URL is HTTP, but favicon should be fetched via HTTPS
            result = fetch_favicon_url("http://example.com/rss", timeout=3)

            self.assertEqual(result, "https://example.com/favicon.ico")
            self.assertTrue(result.startswith("https://"))

    def test_fetch_favicon_url_ssl_failure(self):
        """Test that SSL errors result in empty string."""
        with patch("tasks.favicon_fetcher.requests.head") as mock_head:
            # Mock SSL error
            import requests

            mock_head.side_effect = requests.exceptions.SSLError(
                "SSL verification failed"
            )

            result = fetch_favicon_url("https://example.com/rss", timeout=3)

            # Should return empty string on SSL failure
            self.assertEqual(result, "")

    def test_fetch_favicon_url_no_fallback_to_unverified(self):
        """Test that we don't fall back to default URL if verification fails."""
        with patch("tasks.favicon_fetcher.requests.head") as mock_head:
            # Mock 404 for all paths
            mock_response = Mock()
            mock_response.status_code = 404
            mock_head.return_value = mock_response

            result = fetch_favicon_url("https://example.com/rss", timeout=1)

            # Should return empty string, not a default unverified URL
            self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
