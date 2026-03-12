import unittest
import sys
from unittest.mock import MagicMock, patch
from types import SimpleNamespace


class TestChatRoutesRefactor(unittest.TestCase):
    def setUp(self):
        # Patch sys.modules to mock dependencies dynamically
        self.modules_patcher = patch.dict(
            sys.modules,
            {
                "flask": MagicMock(),
                "mcp": MagicMock(),
                "mcp.client.sse": MagicMock(),
                "api.llm.factory": MagicMock(),
                "api.db": MagicMock(),
                "api.auth": MagicMock(),
                "httpx": MagicMock(),
                "bleach": MagicMock(clean=lambda value, strip=True: value),
                "bs4": MagicMock(),
            },
        )
        self.modules_patcher.start()

        # Now import the module under test inside the test method or setup
        # We need to reload it if it was already imported, or import it fresh
        # But standard import caching makes this tricky.
        # Since we want to test logic that doesn't depend on the mocks at module level,
        # we can perhaps import the specific functions.

        # However, api.chat_routes imports these things at top level.
        # So we must import it AFTER patching.
        import api.chat_routes
        import importlib

        importlib.reload(api.chat_routes)
        self.chat_routes = api.chat_routes

    def tearDown(self):
        self.modules_patcher.stop()

    def test_convert_to_openai_tools(self):
        mcp_tool = SimpleNamespace(
            name="test", description="desc", inputSchema={"type": "object"}
        )
        mcp_tools = SimpleNamespace(tools=[mcp_tool])

        openai_tools = self.chat_routes._convert_to_openai_tools(mcp_tools)
        self.assertEqual(len(openai_tools), 1)
        self.assertEqual(openai_tools[0]["function"]["name"], "test")
        self.assertEqual(openai_tools[0]["function"]["parameters"], {"type": "object"})

    def test_ensure_system_message_inserts(self):
        messages = [{"role": "user", "content": "hello"}]
        self.chat_routes._ensure_system_message(messages)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], self.chat_routes.SYSTEM_PROMPT)

    def test_ensure_system_message_appends(self):
        messages = [{"role": "system", "content": "Existing"}]
        self.chat_routes._ensure_system_message(messages)
        self.assertEqual(len(messages), 1)
        self.assertIn("Existing", messages[0]["content"])
        self.assertIn(self.chat_routes.SYSTEM_PROMPT, messages[0]["content"])

    def test_extract_tool_calls(self):
        content = 'Some text {"name": "test_tool", "parameters": {"arg": 1}} end'
        tools = self.chat_routes.extract_tool_calls_from_content(content)
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "test_tool")

    def test_create_mock_tool_calls(self):
        extracted = [{"name": "test_tool", "parameters": {"arg": 1}}]
        tool_calls, mock_data = self.chat_routes._create_mock_tool_calls(extracted)

        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].function.name, "test_tool")
        self.assertIsInstance(tool_calls[0], SimpleNamespace)

        self.assertEqual(len(mock_data), 1)
        self.assertEqual(mock_data[0]["function"]["name"], "test_tool")

    def test_create_http_client(self):
        # httpx is mocked
        client = self.chat_routes._create_http_client()
        self.assertTrue(client)

    def test_build_context_preamble_for_article(self):
        context = {
            "type": "article",
            "entity_id": "article-1",
            "entity_data": {
                "title": "TPS pyytää lisää tukea",
                "feed_title": "Helsingin Sanomat",
                "published": "2026-03-12T10:00:00Z",
                "language": "fi",
                "summary": "Article summary text",
                "issues": [
                    {"logos": "TPS economy"},
                    {"logos": "Hockey financing"},
                ],
            },
        }

        preamble = self.chat_routes._build_context_preamble(context)
        self.assertIn("Context type: article", preamble)
        self.assertIn("Article title: TPS pyytää lisää tukea", preamble)
        self.assertIn("Article summary: Article summary text", preamble)
        self.assertIn("Currently linked issues: TPS economy, Hockey financing", preamble)

    def test_derive_context_session_title(self):
        context = {
            "type": "issue",
            "entity_data": {"logos": "US-Israel-Iran Bombing Campaign"},
        }

        title = self.chat_routes._derive_context_session_title(context, "fallback")
        self.assertEqual(title, "Issue: US-Israel-Iran Bombing Campaign")


if __name__ == "__main__":
    unittest.main()
