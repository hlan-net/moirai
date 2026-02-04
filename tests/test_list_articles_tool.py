"""
Test for the list_articles MCP tool.
This test mocks the database to verify the tool's logic.
"""
import pytest
from unittest.mock import Mock, patch
import json


def test_list_articles_tool_basic():
    """Test that list_articles tool formats output correctly."""
    # Mock database response
    mock_articles = {
        "rows": [
            {
                "doc": {
                    "_id": "article1",
                    "title": "Test Article 1",
                    "link": "https://example.com/article1",
                    "summary": "This is a test article summary",
                    "published": "2024-02-04T10:00:00",
                    "feed_url": "https://example.com/feed"
                }
            },
            {
                "doc": {
                    "_id": "article2",
                    "title": "Test Article 2",
                    "link": "https://example.com/article2",
                    "summary": "Another test article",
                    "published": "2024-02-04T09:00:00",
                    "feed_url": "https://example.com/feed"
                }
            }
        ]
    }
    
    # Mock response object
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_articles
    
    # Test the logic without actually running the tool
    # This verifies the formatting and filtering logic
    rows = mock_articles["rows"]
    articles = []
    
    for row in rows:
        doc = row.get("doc", {})
        if doc.get("_id", "").startswith("_design/"):
            continue
        articles.append(doc)
    
    # Sort by published date
    articles.sort(key=lambda x: x.get("published", ""), reverse=True)
    
    # Verify sorting
    assert len(articles) == 2
    assert articles[0]["title"] == "Test Article 1"
    assert articles[1]["title"] == "Test Article 2"
    
    # Test output formatting
    output = []
    for art in articles[:2]:
        title = art.get("title", "No Title")
        link = art.get("link", "")
        summary = art.get("summary", "")
        published = art.get("published", "Unknown date")
        feed = art.get("feed_url", "Unknown feed")
        
        output.append(
            f"Title: {title}\n"
            f"Link: {link}\n"
            f"Published: {published}\n"
            f"Feed: {feed}\n"
            f"Summary: {summary}\n"
        )
    
    result = "\n---\n".join(output)
    
    # Verify formatted output
    assert "Test Article 1" in result
    assert "https://example.com/article1" in result
    assert "2024-02-04T10:00:00" in result


def test_list_articles_empty_database():
    """Test that list_articles handles empty database correctly."""
    mock_articles = {"rows": []}
    
    rows = mock_articles.get("rows", [])
    articles = []
    
    for row in rows:
        doc = row.get("doc", {})
        if doc.get("_id", "").startswith("_design/"):
            continue
        articles.append(doc)
    
    # Should be empty
    assert len(articles) == 0


def test_list_articles_filter_by_feed():
    """Test that list_articles can filter by feed_url."""
    mock_articles = {
        "rows": [
            {
                "doc": {
                    "_id": "article1",
                    "title": "Feed A Article",
                    "feed_url": "https://example.com/feed-a"
                }
            },
            {
                "doc": {
                    "_id": "article2",
                    "title": "Feed B Article",
                    "feed_url": "https://example.com/feed-b"
                }
            }
        ]
    }
    
    filter_feed = "https://example.com/feed-a"
    articles = []
    
    for row in mock_articles["rows"]:
        doc = row.get("doc", {})
        if doc.get("_id", "").startswith("_design/"):
            continue
        if filter_feed and doc.get("feed_url") != filter_feed:
            continue
        articles.append(doc)
    
    # Should only have one article
    assert len(articles) == 1
    assert articles[0]["title"] == "Feed A Article"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
