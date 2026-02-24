import unittest
from unittest.mock import MagicMock, patch
import sys
import json
from types import SimpleNamespace

# Mock google.genai before importing gemini provider
mock_genai = MagicMock()
mock_types = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = mock_genai
sys.modules["google.genai.types"] = mock_types

from api.llm.gemini import GeminiProvider  # noqa: E402


class TestGeminiProvider(unittest.TestCase):
    @patch("api.llm.gemini.genai.Client")
    def test_list_models(self, mock_client_class):
        mock_client = mock_client_class.return_value
        m1 = MagicMock()
        m1.name = "models/gemini-pro"
        m1.supported_generation_methods = ["generateContent"]

        m2 = MagicMock()
        m2.name = "models/embedding-001"
        m2.supported_generation_methods = ["embedContent"]

        mock_client.models.list.return_value = [m1, m2]

        provider = GeminiProvider(api_key="test")
        models = provider.list_models()
        self.assertEqual(models, ["gemini-pro"])

    @patch("api.llm.gemini.genai.Client")
    def test_list_models_error(self, mock_client_class):
        mock_client = mock_client_class.return_value
        mock_client.models.list.side_effect = Exception("API Error")

        provider = GeminiProvider(api_key="test")

        with self.assertRaises(Exception):
            provider.list_models()

    @patch("api.llm.gemini.genai.Client")
    @patch("api.llm.gemini.types")
    def test_create_chat_completion_text(self, mock_types, mock_client_class):
        mock_client = mock_client_class.return_value
        
        # Mock response
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Hello there"
        mock_part.function_call = None
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        # Mock Content and Part creation
        mock_types.Part.side_effect = lambda text=None, function_call=None, function_response=None: SimpleNamespace(text=text, function_call=function_call, function_response=function_response)
        mock_types.Content.side_effect = lambda role=None, parts=None: SimpleNamespace(role=role, parts=parts)

        provider = GeminiProvider(api_key="test")
        messages = [{"role": "user", "content": "Hi"}]

        response = provider.create_chat_completion(
            messages, "gemini-pro", tools=None, tool_choice=None
        )

        self.assertEqual(response.choices[0].message.content, "Hello there")
        self.assertIsNone(response.choices[0].message.tool_calls)

        # Verify call arguments
        mock_client.models.generate_content.assert_called_once()
        _, kwargs = mock_client.models.generate_content.call_args
        self.assertEqual(kwargs["model"], "models/gemini-pro")
        contents = kwargs["contents"]
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0].role, "user")
        self.assertEqual(contents[0].parts[0].text, "Hi")

    @patch("api.llm.gemini.genai.Client")
    def test_create_chat_completion_tool_call(self, mock_client_class):
        mock_client = mock_client_class.return_value
        
        # Mock response with function call
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()
        mock_part.text = None
        mock_part.function_call = SimpleNamespace(
            name="get_weather", args={"location": "London"}
        )
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        provider = GeminiProvider(api_key="test")
        messages = [{"role": "user", "content": "Weather?"}]

        response = provider.create_chat_completion(
            messages, "gemini-pro", tools=[], tool_choice="auto"
        )

        tool_calls = response.choices[0].message.tool_calls
        self.assertIsNotNone(tool_calls)
        self.assertEqual(tool_calls[0].function.name, "get_weather")
        self.assertEqual(
            json.loads(tool_calls[0].function.arguments), {"location": "London"}
        )

    @patch("api.llm.gemini.genai.Client")
    @patch("api.llm.gemini.types")
    def test_history_conversion_with_tools(self, mock_types, mock_client_class):
        mock_client = mock_client_class.return_value
        mock_client.models.generate_content.return_value = MagicMock(
            candidates=[MagicMock(content=MagicMock(parts=[MagicMock(text="ok", function_call=None)]))]
        )

        # Mock Content and Part creation
        mock_types.Part.side_effect = lambda text=None, function_call=None, function_response=None: SimpleNamespace(text=text, function_call=function_call, function_response=function_response)
        mock_types.Content.side_effect = lambda role=None, parts=None: SimpleNamespace(role=role, parts=parts)
        mock_types.FunctionCall.side_effect = lambda name=None, args=None: SimpleNamespace(name=name, args=args)
        mock_types.FunctionResponse.side_effect = lambda name=None, response=None: SimpleNamespace(name=name, response=response)

        provider = GeminiProvider(api_key="test")
        messages = [
            {"role": "user", "content": "What's the weather?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "Paris"}',
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "name": "get_weather",
                "content": '{"temp": 15}',
            },  # Function response
        ]

        provider.create_chat_completion(
            messages, "gemini-pro", tools=[], tool_choice="auto"
        )

        # Check generate_content contents argument
        _, kwargs = mock_client.models.generate_content.call_args
        contents = kwargs["contents"]

        # Item 0: User
        self.assertEqual(contents[0].role, "user")
        self.assertEqual(contents[0].parts[0].text, "What's the weather?")

        # Item 1: Model (Assistant) calling function
        self.assertEqual(contents[1].role, "model")
        self.assertEqual(contents[1].parts[0].function_call.name, "get_weather")

        # Item 2: User (Function Response)
        self.assertEqual(contents[2].role, "user")
        self.assertEqual(contents[2].parts[0].function_response.name, "get_weather")


if __name__ == "__main__":
    unittest.main()
