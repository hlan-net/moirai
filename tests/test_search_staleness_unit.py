import os
os.environ.setdefault("ADMIN_PASSWORD", "test_password")

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
    userspace = "00000000-0000-0000-0000-000000000000"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "docs": [
            {"_id": "issue_1", "logos": "Test Logos", "description": "Test Desc", "premises": [], "longevity": "transient", "status": "active"}
        ]
    }
    mock_db['request'].return_value = mock_response
    
    with patch('mcp_service.core.ADMIN_PASSWORD', 'test_password'):
        result = search_issues(query="test", userspace=userspace)
    
    data = json.loads(result)
    assert data["total"] == 1
    assert data["results"][0]["logos"] == "Test Logos"
    mock_db['request'].assert_called_once()
    _, kwargs = mock_db['request'].call_args
    userspace_selector = kwargs['json_data']['selector']['$and'][0]['$or']
    assert {"userspace": userspace} in userspace_selector

def test_search_events_alias_unit(mock_db):
    userspace = "00000000-0000-0000-0000-000000000000"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"docs": []}
    mock_db['request'].return_value = mock_response
    
    with patch('mcp_service.core.ADMIN_PASSWORD', 'test_password'):
        search_events(query="test", userspace=userspace)
    
    mock_db['request'].assert_called_once()
    _, kwargs = mock_db['request'].call_args
    # Verify it filters by transient longevity
    selector = kwargs['json_data']['selector']
    conditions = selector.get('$and', [selector])
    assert any(condition.get('longevity') == "transient" for condition in conditions)

def test_mark_entity_stale_unit(mock_db):
    entity_id = "issue_123"
    userspace = "00000000-0000-0000-0000-000000000000"
    mock_db['fetch'].return_value = {"_id": entity_id, "is_stale": False, "userspace": userspace}
    mock_db['update'].return_value = True
    
    result = mark_entity_stale(entity_type="event", entity_id=entity_id, is_stale=True, userspace=userspace)
    
    assert result["status"] == "success"
    mock_db['fetch'].assert_called_once_with("issues", entity_id) # Verify it uses issues DB
    mock_db['update'].assert_called_once()
    assert mock_db['update'].call_args[0][2]["is_stale"] is True
