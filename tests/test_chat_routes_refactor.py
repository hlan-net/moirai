
import unittest
import sys
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
import json

# Mock dependencies BEFORE importing api.chat_routes
sys.modules['flask'] = MagicMock()
sys.modules['mcp'] = MagicMock()
sys.modules['mcp.client.sse'] = MagicMock()
sys.modules['api.llm.factory'] = MagicMock()
sys.modules['api.db'] = MagicMock()
sys.modules['httpx'] = MagicMock()

# Now import the functions to test
# We need to use 'from api.chat_routes import ...' but since we mocked dependencies, 
# the imports inside chat_routes will return mocks.
from api.chat_routes import _ensure_system_message, _create_mock_tool_calls, extract_tool_calls_from_content, _create_http_client, _convert_to_openai_tools
from api.chat_routes import SYSTEM_PROMPT

class TestChatRoutesRefactor(unittest.TestCase):
    def test_convert_to_openai_tools(self):
        mcp_tool = SimpleNamespace(
            name="test", 
            description="desc", 
            inputSchema={"type": "object"}
        )
        mcp_tools = SimpleNamespace(tools=[mcp_tool])
        
        openai_tools = _convert_to_openai_tools(mcp_tools)
        self.assertEqual(len(openai_tools), 1)
        self.assertEqual(openai_tools[0]["function"]["name"], "test")
        self.assertEqual(openai_tools[0]["function"]["parameters"], {"type": "object"})

    def test_ensure_system_message_inserts(self):
        messages = [{"role": "user", "content": "hello"}]
        _ensure_system_message(messages)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], SYSTEM_PROMPT)

    def test_ensure_system_message_appends(self):
        messages = [{"role": "system", "content": "Existing"}]
        _ensure_system_message(messages)
        self.assertEqual(len(messages), 1)
        self.assertIn("Existing", messages[0]["content"])
        self.assertIn(SYSTEM_PROMPT, messages[0]["content"])

    def test_extract_tool_calls(self):
        content = 'Some text {"name": "test_tool", "parameters": {"arg": 1}} end'
        tools = extract_tool_calls_from_content(content)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "test_tool")
        
    def test_create_mock_tool_calls(self):
        extracted = [{"name": "test_tool", "parameters": {"arg": 1}}]
        tool_calls, mock_data = _create_mock_tool_calls(extracted)
        
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].function.name, "test_tool")
        self.assertIsInstance(tool_calls[0], SimpleNamespace)
        
        self.assertEqual(len(mock_data), 1)
        self.assertEqual(mock_data[0]["function"]["name"], "test_tool")
        
    def test_create_http_client(self):
        # httpx is mocked, so _create_http_client will return a mock or call the mocked AsyncClient
        client = _create_http_client()
        self.assertTrue(client)

if __name__ == '__main__':
    unittest.main()
