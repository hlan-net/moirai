import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from tasks.agent_orchestrator import AgentOrchestrator
from api.validation import AgentStatus, AgentTriggerType

@pytest.fixture
def mock_redis():
    return MagicMock()

@pytest.fixture
def orchestrator(mock_redis):
    orch = AgentOrchestrator(interval=1, redis_client=mock_redis)
    return orch

def test_orchestrator_initialization(orchestrator, mock_redis):
    assert orchestrator.interval == 1
    assert orchestrator.redis_client == mock_redis
    assert orchestrator.is_leader is False
    assert isinstance(orchestrator.leader_id, str)

def test_acquire_lock_success(orchestrator, mock_redis):
    mock_redis.set.return_value = True
    assert orchestrator._acquire_lock() is True
    mock_redis.set.assert_called_once_with(
        orchestrator.lock_name, 
        orchestrator.leader_id, 
        nx=True, 
        ex=orchestrator.lock_expiry
    )

def test_acquire_lock_failure(orchestrator, mock_redis):
    mock_redis.set.return_value = False
    assert orchestrator._acquire_lock() is False

def test_renew_lock_success(orchestrator, mock_redis):
    mock_redis.eval.return_value = 1
    assert orchestrator._renew_lock() is True

def test_renew_lock_failure(orchestrator, mock_redis):
    mock_redis.eval.return_value = 0
    assert orchestrator._renew_lock() is False

def test_release_lock(orchestrator, mock_redis):
    orchestrator.is_leader = True
    orchestrator._release_lock()
    assert orchestrator.is_leader is False
    mock_redis.eval.assert_called_once()

@patch('tasks.agent_orchestrator.query_couchdb')
@patch('tasks.agent_orchestrator.update_couchdb_doc')
def test_check_and_run_agents_scheduled(mock_update, mock_query, orchestrator):
    # Setup mock agent config
    agent_id = "test-agent"
    last_run = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    agent_config = {
        "_id": agent_id,
        "userspace": "00000000-0000-0000-0000-000000000000",
        "status": AgentStatus.ACTIVE.value,
        "trigger_type": AgentTriggerType.SCHEDULED.value,
        "schedule_interval": "1h",
        "last_run_at": last_run,
        "logic_module": "tasks.agent_logic.check_event_staleness"
    }
    mock_query.return_value = [agent_config]
    
    with patch.object(orchestrator, 'execute_agent_logic') as mock_execute:
        orchestrator.check_and_run_agents()
        mock_execute.assert_called_once_with(agent_config, llm_config=None)

def test_is_scheduled_agent_due(orchestrator):
    now = datetime.now(timezone.utc)
    
    # Due: last run 2 hours ago, interval 1h
    last_run_str = (now - timedelta(hours=2)).isoformat()
    assert orchestrator.is_scheduled_agent_due(last_run_str, "1h") is True
    
    # Not due: last run 30 mins ago, interval 1h
    last_run_str = (now - timedelta(minutes=30)).isoformat()
    assert orchestrator.is_scheduled_agent_due(last_run_str, "1h") is False
    
    # Test different units
    assert orchestrator.is_scheduled_agent_due((now - timedelta(seconds=70)).isoformat(), "60s") is True
    assert orchestrator.is_scheduled_agent_due((now - timedelta(days=2)).isoformat(), "1d") is True

@patch('importlib.import_module')
@patch('tasks.agent_orchestrator.update_couchdb_doc')
def test_execute_agent_logic(mock_update, mock_import, orchestrator):
    mock_module = MagicMock()
    mock_func = MagicMock()
    # Use a whitelisted module name
    whitelisted_module = "tasks.agent_logic"
    whitelisted_func = "create_event_from_articles"
    
    setattr(mock_module, whitelisted_func, mock_func)
    mock_import.return_value = mock_module
    
    agent_config = {
        "_id": "agent1",
        "logic_module": f"{whitelisted_module}.{whitelisted_func}"
    }
    
    orchestrator.execute_agent_logic(agent_config)
    
    mock_import.assert_called_once_with(whitelisted_module)
    mock_func.assert_called_once()
    mock_update.assert_called_once()
    assert "last_run_at" in agent_config
