"""
Test that the chat agent properly injects API key into MCP tool calls.
"""
import pytest
import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# Set environment variable before importing
os.environ['API_PASSWORD'] = 'test_password_123'

from api.chat_routes import _execute_tool_calls


@pytest.mark.asyncio
async def test_api_key_injection():
    """Test that _execute_tool_calls injects api_key into function arguments."""
    
    # Create mock session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text="Success")]
    mock_session.call_tool.return_value = mock_result
    
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
    
    # Extract the arguments dictionary
    func_args = call_args[0][1]  # Second positional argument
    
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
async def test_api_key_injection_multiple_tools():
    """Test that api_key is injected for multiple tool calls."""
    
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text="Success")]
    mock_session.call_tool.return_value = mock_result
    
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
        func_args = call[0][1]
        assert "api_key" in func_args
        assert func_args["api_key"] == "test_password_123"
        assert func_args["param"] == f"value_{i}"
    
    # Verify all results were added to messages
    assert len(messages) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
