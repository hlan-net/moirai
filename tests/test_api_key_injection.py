"""
Test that the chat agent properly injects API key into MCP tool calls.
"""
import pytest
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from api.chat_routes import _execute_tool_calls


@pytest.fixture
def setup_api_password_env(monkeypatch):
    """Fixture to set API_PASSWORD environment variable for testing."""
    monkeypatch.setenv('API_PASSWORD', 'test_password_123')


@pytest.fixture
def mock_session():
    """Fixture to create a mock MCP session."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text="Success")]
    session.call_tool.return_value = mock_result
    return session


@pytest.mark.asyncio
async def test_api_key_injection(setup_api_password_env, mock_session):
    """Test that _execute_tool_calls injects api_key into function arguments."""
    
    # Create mock tool call
    mock_tool_call = SimpleNamespace(
        id="call_123",
        function=SimpleNamespace(
            name="search_articles",
            arguments=json.dumps({"query": "test", "namespace": "test-guid"})
        )
    )
    
    messages = []
    
    # Execute tool calls
    await _execute_tool_calls(mock_session, [mock_tool_call], messages)
    
    # Verify that call_tool was called with api_key injected
    mock_session.call_tool.assert_called_once()
    call_args = mock_session.call_tool.call_args
    
    # Extract the arguments dictionary (second positional argument to call_tool)
    func_args = call_args.args[1]
    
    # Verify api_key was injected
    assert "api_key" in func_args, "api_key should be injected into tool arguments"
    assert func_args["api_key"] == "test_password_123", "api_key should match API_PASSWORD"
    
    # Verify original arguments are preserved
    assert func_args["query"] == "test"
    assert func_args["namespace"] == "test-guid"
    
    # Verify tool result was added to messages
    assert len(messages) == 1
    assert messages[0]["role"] == "tool"
    assert messages[0]["name"] == "search_articles"
    assert messages[0]["tool_call_id"] == "call_123"
    assert messages[0]["content"] == "Success"


@pytest.mark.asyncio
async def test_api_key_injection_multiple_tools(setup_api_password_env, mock_session):
    """Test that api_key is injected for multiple tool calls."""
    
    # Create multiple tool calls
    tool_calls = [
        SimpleNamespace(
            id=f"call_{i}",
            function=SimpleNamespace(
                name=f"tool_{i}",
                arguments=json.dumps({"param": f"value_{i}"})
            )
        )
        for i in range(3)
    ]
    
    messages = []
    
    await _execute_tool_calls(mock_session, tool_calls, messages)
    
    # Verify call_tool was called 3 times, each with api_key
    assert mock_session.call_tool.call_count == 3
    
    for i, call in enumerate(mock_session.call_tool.call_args_list):
        func_args = call.args[1]  # Second positional argument
        assert "api_key" in func_args
        assert func_args["api_key"] == "test_password_123"
        assert func_args["param"] == f"value_{i}"
    
    # Verify all results were added to messages
    assert len(messages) == 3


@pytest.mark.asyncio
async def test_api_key_not_overwritten_if_present(setup_api_password_env, mock_session):
    """Test that existing api_key in arguments is not overwritten."""
    
    # Create tool call with existing api_key
    mock_tool_call = SimpleNamespace(
        id="call_123",
        function=SimpleNamespace(
            name="search_articles",
            arguments=json.dumps({
                "query": "test",
                "namespace": "test-guid",
                "api_key": "existing_key"  # Already has api_key
            })
        )
    )
    
    messages = []
    
    await _execute_tool_calls(mock_session, [mock_tool_call], messages)
    
    # Verify that existing api_key was preserved
    call_args = mock_session.call_tool.call_args
    func_args = call_args.args[1]  # Second positional argument
    assert func_args["api_key"] == "existing_key", "Existing api_key should not be overwritten"


@pytest.mark.asyncio
async def test_api_key_missing_env_var(monkeypatch, mock_session):
    """Test behavior when API_PASSWORD is not set."""
    
    # Remove API_PASSWORD from environment
    monkeypatch.delenv('API_PASSWORD', raising=False)
    
    mock_tool_call = SimpleNamespace(
        id="call_123",
        function=SimpleNamespace(
            name="search_articles",
            arguments=json.dumps({"query": "test", "namespace": "test-guid"})
        )
    )
    
    messages = []
    
    # Should still execute but log error and not inject api_key
    await _execute_tool_calls(mock_session, [mock_tool_call], messages)
    
    # Verify call_tool was still called
    mock_session.call_tool.assert_called_once()
    
    # Verify api_key was NOT injected
    call_args = mock_session.call_tool.call_args
    func_args = call_args.args[1]  # Second positional argument
    assert "api_key" not in func_args, "api_key should not be injected when API_PASSWORD is missing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
