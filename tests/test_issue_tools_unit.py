import os
os.environ.setdefault("ADMIN_PASSWORD", "test_password")

import pytest
from unittest.mock import patch, MagicMock
from mcp_service.tools.issues import forge_issue, add_event, add_trend, list_issues, list_events

@pytest.fixture
def mock_db():
    with patch('mcp_service.tools.issues.store_doc') as mock_store, \
         patch('mcp_service.tools.issues.db_request') as mock_request, \
         patch('mcp_service.tools.issues.get_doc') as mock_get, \
         patch('mcp_service.tools.issues.update_doc') as mock_update:
        yield {
            'store': mock_store,
            'request': mock_request,
            'get': mock_get,
            'update': mock_update
        }

def test_forge_issue_unit(mock_db):
    mock_db['store'].return_value = "issue_123"
    userspace = "00000000-0000-0000-0000-000000000000"
    
    with patch('mcp_service.core.ADMIN_PASSWORD', 'test_password'):
        result = forge_issue(
            logos="Test Logos",
            description="Test Desc",
            premises=[{"type": "message", "id": "msg_1"}],
            userspace=userspace,
            longevity="transient",
        )
    
    # Check new standardized response format
    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert result["data"]["issue_id"] == "issue_123"
    assert result["data"]["logos"] == "Test Logos"
    assert result["data"]["longevity"] == "transient"
    assert result["data"]["premises_count"] == 1
    
    mock_db['store'].assert_called_once()
    args, _ = mock_db['store'].call_args
    assert args[0] == "issues"
    assert args[1]["logos"] == "Test Logos"
    assert args[1]["longevity"] == "transient"

def test_add_event_alias_unit(mock_db):
    mock_db['store'].return_value = "event_123"
    userspace = "00000000-0000-0000-0000-000000000000"
    
    with patch('mcp_service.core.ADMIN_PASSWORD', 'test_password'):
        result = add_event(
            name="Test Event",
            description="Event Desc",
            article_links=["http://link1.com"],
            userspace=userspace,
        )
    
    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert result["data"]["issue_id"] == "event_123"
    assert result["data"]["logos"] == "Test Event"
    assert result["data"]["longevity"] == "transient"
    mock_db['store'].assert_called_once()
    args, _ = mock_db['store'].call_args
    assert args[0] == "issues"  # Verify it uses issues DB
    assert args[1]["logos"] == "Test Event"
    assert args[1]["longevity"] == "transient"
    assert args[1]["premises"] == [{"type": "message", "id": "http://link1.com"}]

def test_add_trend_alias_unit(mock_db):
    mock_db['store'].return_value = "trend_123"
    userspace = "00000000-0000-0000-0000-000000000000"
    
    with patch('mcp_service.core.ADMIN_PASSWORD', 'test_password'):
        result = add_trend(
            name="Test Trend",
            description="Trend Desc",
            event_ids=["event_1"],
            userspace=userspace,
        )
    
    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert result["data"]["issue_id"] == "trend_123"
    assert result["data"]["logos"] == "Test Trend"
    assert result["data"]["longevity"] == "temporal"
    mock_db['store'].assert_called_once()
    args, _ = mock_db['store'].call_args
    assert args[0] == "issues"  # Verify it uses issues DB
    assert args[1]["logos"] == "Test Trend"
    assert args[1]["longevity"] == "temporal"
    assert args[1]["premises"] == [{"type": "issue", "id": "event_1"}]

def test_list_issues_unit(mock_db):
    userspace = "00000000-0000-0000-0000-000000000000"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "docs": [
            {"_id": "issue_1", "logos": "Logos 1", "longevity": "transient", "status": "active", "premises": []}
        ]
    }
    mock_db['request'].return_value = mock_response
    
    with patch('mcp_service.core.ADMIN_PASSWORD', 'test_password'):
        result = list_issues(userspace=userspace)
    
    # Check new standardized response format
    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert result["data"]["count"] == 1
    assert result["data"]["issues"][0]["id"] == "issue_1"
    assert result["data"]["issues"][0]["logos"] == "Logos 1"
    assert result["data"]["issues"][0]["longevity"] == "transient"
    
    mock_db['request'].assert_called_once()
    _, kwargs = mock_db['request'].call_args
    assert {"userspace": userspace} in kwargs['json_data']['selector']['$or']

def test_list_events_alias_unit(mock_db):
    userspace = "00000000-0000-0000-0000-000000000000"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"docs": []}
    mock_db['request'].return_value = mock_response
    
    with patch('mcp_service.core.ADMIN_PASSWORD', 'test_password'):
        list_events(userspace=userspace)
    
    mock_db['request'].assert_called_once()
    _, kwargs = mock_db['request'].call_args
    # Verify it filters by transient longevity
    assert kwargs['json_data']['selector']['longevity'] == "transient"


def test_forge_issue_defaults_to_deployment_userspace(mock_db):
    mock_db['store'].return_value = "issue_456"
    default_userspace = "11111111-1111-4111-8111-111111111111"

    with patch('mcp_service.core.get_default_userspace', return_value=default_userspace):
        result = forge_issue(
            logos="No userspace given",
            description="Desc",
            premises=[],
        )

    assert result["status"] == "success"
    stored = mock_db['store'].call_args[0][1]
    assert stored["userspace"] == default_userspace


def test_forge_issue_without_userspace_or_default_fails(mock_db):
    with patch('mcp_service.core.get_default_userspace', return_value=None):
        result = forge_issue(logos="x", description="y", premises=[])

    assert result["status"] == "error"
    assert "DEFAULT_USERSPACE" in str(result)
    mock_db['store'].assert_not_called()
