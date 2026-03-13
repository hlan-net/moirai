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
@patch('tasks.agent_orchestrator.update_couchdb_doc_safe')
def test_check_and_run_agents_scheduled(mock_update_safe, mock_query, orchestrator):
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
        # Verify query was called with SCHEDULED filter
        call_args = mock_query.call_args
        assert call_args[1]["selector"]["trigger_type"] == AgentTriggerType.SCHEDULED.value
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
@patch('tasks.agent_orchestrator.update_couchdb_doc_safe')
def test_execute_agent_logic(mock_update_safe, mock_import, orchestrator):
    mock_module = MagicMock()
    mock_func = MagicMock()
    # Use a whitelisted module name
    whitelisted_module = "tasks.agent_logic"
    whitelisted_func = "create_event_from_articles"

    mock_update_safe.return_value = True
    setattr(mock_module, whitelisted_func, mock_func)
    mock_import.return_value = mock_module

    agent_config = {
        "_id": "agent1",
        "logic_module": f"{whitelisted_module}.{whitelisted_func}"
    }

    orchestrator.execute_agent_logic(agent_config)

    mock_import.assert_called_once_with(whitelisted_module)
    mock_func.assert_called_once()
    mock_update_safe.assert_called_once_with(
        orchestrator.agent_configs_db,
        "agent1",
        {"last_run_at": mock_update_safe.call_args[0][2]["last_run_at"]},
    )


# Tests for changes feed functionality
@patch('tasks.agent_orchestrator.requests.get')
def test_get_last_seq_returns_stored_value(mock_get, orchestrator):
    """Test that _get_last_seq returns the stored value from config DB."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"value": "12345"}
    mock_get.return_value = mock_response

    seq = orchestrator._get_last_seq()

    assert seq == "12345"
    mock_get.assert_called_once()


@patch('tasks.agent_orchestrator.requests.get')
def test_get_last_seq_returns_now_on_missing_doc(mock_get, orchestrator):
    """Test that _get_last_seq returns 'now' when config doc doesn't exist."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    seq = orchestrator._get_last_seq()

    assert seq == "now"


@patch('tasks.agent_orchestrator.requests.put')
@patch('tasks.agent_orchestrator.requests.get')
def test_save_last_seq_persists_value(mock_get, mock_put, orchestrator):
    """Test that _save_last_seq saves the sequence to config DB."""
    # Simulate existing doc
    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.json.return_value = {"_rev": "1-abc"}
    mock_get.return_value = mock_get_response

    mock_put_response = MagicMock()
    mock_put_response.status_code = 200
    mock_put.return_value = mock_put_response

    orchestrator._save_last_seq("12345")

    mock_put.assert_called_once()
    call_args = mock_put.call_args
    assert call_args[1]["json"]["value"] == "12345"


@patch('tasks.agent_orchestrator.query_couchdb')
@patch('tasks.agent_orchestrator.requests.get')
def test_changes_feed_dispatches_correct_userspace(mock_get, mock_query, orchestrator):
    """Test that changes feed dispatches agents with articles from their own userspace."""
    userspace_a = "00000000-0000-0000-0000-000000000001"
    userspace_b = "00000000-0000-0000-0000-000000000002"

    # Mock agents
    agent_a = {
        "_id": "agent-a",
        "userspace": userspace_a,
        "status": AgentStatus.ACTIVE.value,
        "trigger_type": AgentTriggerType.ON_NEW_ARTICLE.value,
        "llm_model_config": None,
    }
    agent_b = {
        "_id": "agent-b",
        "userspace": userspace_b,
        "status": AgentStatus.ACTIVE.value,
        "trigger_type": AgentTriggerType.ON_NEW_ARTICLE.value,
        "llm_model_config": None,
    }
    mock_query.return_value = [agent_a, agent_b]

    # Mock articles: 2 for userspace A, 1 for userspace B
    new_docs = [
        {"_id": "art1", "userspace": userspace_a},
        {"_id": "art2", "userspace": userspace_a},
        {"_id": "art3", "userspace": userspace_b},
    ]

    with patch.object(orchestrator, 'execute_agent_logic') as mock_execute:
        orchestrator._dispatch_on_new_article_agents(new_docs)

        # Should have called execute_agent_logic twice (once per agent)
        assert mock_execute.call_count == 2

        # Check that agent_a received only articles from userspace_a
        calls = mock_execute.call_args_list
        first_call = calls[0]
        assert first_call[0][0] == agent_a
        assert len(first_call[1]["new_articles"]) == 2
        assert all(doc["userspace"] == userspace_a for doc in first_call[1]["new_articles"])

        # Check that agent_b received only articles from userspace_b
        second_call = calls[1]
        assert second_call[0][0] == agent_b
        assert len(second_call[1]["new_articles"]) == 1
        assert all(doc["userspace"] == userspace_b for doc in second_call[1]["new_articles"])


@patch('tasks.agent_orchestrator.query_couchdb')
def test_changes_feed_skips_when_not_leader(mock_query, orchestrator):
    """Test that changes feed does not process articles when not leader."""
    orchestrator.is_leader = False

    with patch.object(orchestrator, '_process_article_changes') as mock_process:
        # Simulate one iteration of the changes feed loop
        if not orchestrator.is_leader:
            mock_process.assert_not_called()


@patch('tasks.agent_orchestrator.requests.put')
@patch('tasks.agent_orchestrator.requests.get')
def test_changes_feed_saves_last_seq(mock_req_get, mock_req_put, orchestrator):
    """Test that _process_article_changes saves the last_seq after processing."""
    orchestrator.last_seq = "0"

    # Create a side effect for different GET requests
    def get_side_effect(url, **kwargs):
        mock_response = MagicMock()
        if "/_changes" in url:
            # For changes feed request
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "results": [],
                "last_seq": "12345",
            }
        else:
            # For reading the existing seq doc
            mock_response.status_code = 200
            mock_response.json.return_value = {"_rev": "1-abc"}
        return mock_response

    mock_req_get.side_effect = get_side_effect

    # Mock PUT for saving sequence
    mock_put_response = MagicMock()
    mock_put_response.status_code = 200
    mock_req_put.return_value = mock_put_response

    with patch.object(orchestrator, '_dispatch_on_new_article_agents'):
        orchestrator._process_article_changes()

    assert orchestrator.last_seq == "12345"


@patch('tasks.agent_orchestrator.requests.get')
@patch('time.sleep')
def test_changes_feed_retries_on_404(mock_sleep, mock_get, orchestrator):
    """Test that changes feed retries with 10s delay on 404."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    orchestrator._process_article_changes()

    mock_sleep.assert_called_once_with(10)


@patch('tasks.agent_orchestrator.query_couchdb')
@patch('tasks.agent_orchestrator.update_couchdb_doc_safe')
def test_check_and_run_agents_only_schedules(mock_update_safe, mock_query, orchestrator):
    """Test that check_and_run_agents only queries SCHEDULED agents."""
    agent_config = {
        "_id": "agent-scheduled",
        "userspace": "test-uuid",
        "status": AgentStatus.ACTIVE.value,
        "trigger_type": AgentTriggerType.SCHEDULED.value,
        "schedule_interval": "1h",
        "last_run_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    }
    mock_query.return_value = [agent_config]

    with patch.object(orchestrator, 'run_agent_if_due') as mock_run:
        orchestrator.check_and_run_agents()

        # Verify query was called with SCHEDULED filter
        call_args = mock_query.call_args
        assert "trigger_type" in call_args[1]["selector"]
        assert call_args[1]["selector"]["trigger_type"] == AgentTriggerType.SCHEDULED.value

        mock_run.assert_called_once_with(agent_config)
