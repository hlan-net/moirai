import pytest
from unittest.mock import patch, MagicMock
from mcp_service.tools.search import search_issues, search_events
from mcp_service.tools.staleness import mark_entity_stale
import json

@pytest.fixture
def mock_db():
    with patch('mcp_service.tools.search.db_request') as mock_request, \
         patch('mcp_service.tools.staleness.fetch_from_couchdb') as mock_fetch, \
         patch('mcp_service.tools.staleness.update_couchdb_doc') as mock_update:
        yield {
            'request': mock_request,
            'fetch': mock_fetch,
            'update': mock_update
        }

def test_search_issues_unit(mock_db):
    namespace = "00000000-0000-0000-0000-000000000000"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "docs": [
            {"_id": "issue_1", "logos": "Test Logos", "description": "Test Desc", "premises": [], "longevity": "transient", "status": "active"}
        ]
    }
    mock_db['request'].return_value = mock_response
    
    with patch('mcp_service.core.API_PASSWORD', 'test_password'):
        result = search_issues(query="test", namespace=namespace, api_key="test_password")
    
    data = json.loads(result)
    assert data["total"] == 1
    assert data["results"][0]["logos"] == "Test Logos"
    mock_db['request'].assert_called_once()
    _, kwargs = mock_db['request'].call_args
    assert kwargs['json_data']['selector']['namespace'] == namespace

def test_search_events_alias_unit(mock_db):
    namespace = "00000000-0000-0000-0000-000000000000"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"docs": []}
    mock_db['request'].return_value = mock_response
    
    with patch('mcp_service.core.API_PASSWORD', 'test_password'):
        search_events(query="test", namespace=namespace, api_key="test_password")
    
    mock_db['request'].assert_called_once()
    _, kwargs = mock_db['request'].call_args
    # Verify it filters by transient longevity
    assert kwargs['json_data']['selector']['longevity'] == "transient"

def test_mark_entity_stale_unit(mock_db):
    entity_id = "issue_123"
    mock_db['fetch'].return_value = {"_id": entity_id, "is_stale": False}
    mock_db['update'].return_value = True
    
    result = mark_entity_stale(entity_type="event", entity_id=entity_id, is_stale=True)
    
    assert result["status"] == "success"
    mock_db['fetch'].assert_called_once_with("issues", entity_id) # Verify it uses issues DB
    mock_db['update'].assert_called_once()
    assert mock_db['update'].call_args[0][2]["is_stale"] is True
