import pytest
from unittest.mock import patch
from mcp_service.tools.agent_configs import add_agent_config, list_agent_configs
import uuid

@pytest.fixture
def mock_db():
    with patch('mcp_service.tools.agent_configs.update_couchdb_doc') as mock_update, \
         patch('mcp_service.tools.agent_configs.query_couchdb') as mock_query:
        yield {
            'update': mock_update,
            'query': mock_query
        }

def test_add_agent_config_unit(mock_db):
    mock_db['update'].return_value = True
    user_id = str(uuid.uuid4())
    
    result = add_agent_config(
        user_id=user_id,
        name="Test Agent",
        trigger_type="on_new_article",
        target_db="articles",
        logic_module="tasks.agent_logic.create_event"
    )
    
    assert result["status"] == "success"
    assert result["agent_config"]["name"] == "Test Agent"
    mock_db['update'].assert_called_once()

def test_add_agent_config_issues_unit(mock_db):
    mock_db['update'].return_value = True
    user_id = str(uuid.uuid4())
    
    # Test targeting the new issues database
    result = add_agent_config(
        user_id=user_id,
        name="Issue Agent",
        trigger_type="scheduled",
        target_db="issues",
        logic_module="tasks.agent_logic.check_event_staleness",
        schedule_interval="1h"
    )
    
    assert result["status"] == "success"
    assert result["agent_config"]["target_db"] == "issues"
    mock_db['update'].assert_called_once()

def test_list_agent_configs_unit(mock_db):
    mock_db['query'].return_value = [{"_id": "agent_1"}]
    
    result = list_agent_configs(user_id="user_123")
    
    assert result["status"] == "success"
    assert len(result["agent_configs"]) == 1
    mock_db['query'].assert_called_once()
    _, kwargs = mock_db['query'].call_args
    assert kwargs['selector']['user_id'] == "user_123"
