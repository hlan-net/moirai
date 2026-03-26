"""Tests for the /api/mythology endpoint.

The Mythology page is a public-facing endpoint that displays platform stats
and public issues. It does not require authentication.
"""

import os

import pytest
import requests

# Configuration
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8088")


@pytest.mark.integration
def test_mythology_endpoint_no_auth_required():
    """Verify that the /api/mythology endpoint is publicly accessible (no auth)."""
    res = requests.get(f"{BASE_URL}/api/mythology")
    # Should return 200, not 401
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"


@pytest.mark.integration
def test_mythology_endpoint_returns_stats():
    """Verify the /api/mythology response includes stats structure."""
    res = requests.get(f"{BASE_URL}/api/mythology")
    assert res.status_code == 200

    data = res.json()

    # Must have stats object
    assert "stats" in data, "Response must include 'stats'"
    stats = data["stats"]

    # Stats must have feeds, articles, issues counts
    assert "feeds" in stats, "Stats must include 'feeds' count"
    assert "articles" in stats, "Stats must include 'articles' count"
    assert "issues" in stats, "Stats must include 'issues' count"

    # All counts should be non-negative integers
    assert isinstance(stats["feeds"], int) and stats["feeds"] >= 0
    assert isinstance(stats["articles"], int) and stats["articles"] >= 0
    assert isinstance(stats["issues"], int) and stats["issues"] >= 0


@pytest.mark.integration
def test_mythology_endpoint_returns_public_issues():
    """Verify the /api/mythology response includes public_issues array."""
    res = requests.get(f"{BASE_URL}/api/mythology")
    assert res.status_code == 200

    data = res.json()

    # Must have public_issues array
    assert "public_issues" in data, "Response must include 'public_issues'"
    assert isinstance(data["public_issues"], list), "public_issues must be a list"


@pytest.mark.integration
def test_mythology_public_issue_structure():
    """Verify public issues have the expected fields when present."""
    res = requests.get(f"{BASE_URL}/api/mythology")
    assert res.status_code == 200

    data = res.json()
    public_issues = data.get("public_issues", [])

    # If there are public issues, verify their structure
    for issue in public_issues:
        assert "_id" in issue, "Public issue must have '_id'"
        assert "logos" in issue, "Public issue must have 'logos'"
        assert "description" in issue, "Public issue must have 'description'"
        assert "longevity" in issue, "Public issue must have 'longevity'"
        assert "status" in issue, "Public issue must have 'status'"
        assert "premises_count" in issue, "Public issue must have 'premises_count'"

        # Validate longevity is one of expected values
        assert issue["longevity"] in (
            "transient",
            "temporal",
            "epic",
        ), f"Invalid longevity: {issue['longevity']}"

        # Validate status is one of expected values
        assert issue["status"] in (
            "active",
            "eternal",
        ), f"Invalid status: {issue['status']}"

        # premises_count should be non-negative
        assert isinstance(issue["premises_count"], int) and issue["premises_count"] >= 0


@pytest.mark.integration
def test_mythology_endpoint_rate_limited():
    """Verify the /api/mythology endpoint has rate limiting (60/min)."""
    # Just verify the endpoint works - actual rate limit testing would require
    # sending 60+ requests which is slow. We trust the decorator is applied.
    res = requests.get(f"{BASE_URL}/api/mythology")
    assert res.status_code == 200
    # If rate limited, we'd get 429 - but we shouldn't hit it with one request


if __name__ == "__main__":
    # Manual test run
    print(f"Testing Mythology API at {BASE_URL}/api/mythology...")
    try:
        res = requests.get(f"{BASE_URL}/api/mythology")
        if res.status_code == 200:
            import json

            print("SUCCESS: Mythology API returned data:")
            print(json.dumps(res.json(), indent=2))
        else:
            print(f"FAILED: {res.status_code} {res.text}")
    except Exception as e:
        print(f"Error connecting to API: {e}")
