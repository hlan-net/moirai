import unittest
from unittest.mock import MagicMock, patch
import sys
import json
from types import SimpleNamespace

# Mock google.generativeai before importing gemini provider
mock_genai = MagicMock()
mock_genai_types = MagicMock()
mock_genai_google = MagicMock()
sys.modules['google'] = MagicMock()
sys.modules['google.generativeai'] = mock_genai
sys.modules['google.generativeai.types'] = mock_genai_types
sys.modules['google.ai'] = MagicMock()
sys.modules['google.ai.generativelanguage'] = MagicMock()

from api.llm.gemini import GeminiProvider

class TestGeminiProvider(unittest.TestCase):
    @patch('api.llm.gemini.genai')
    def test_list_models(self, mock_genai):
        m1 = MagicMock()
        m1.name = 'models/gemini-pro'
        m1.supported_generation_methods = ['generateContent']
        
        m2 = MagicMock()
        m2.name = 'models/embedding-001'
        m2.supported_generation_methods = ['embedContent']
        
        mock_genai.list_models.return_value = [m1, m2]
        
        provider = GeminiProvider(api_key="test")
        models = provider.list_models()
        self.assertEqual(models, ['gemini-pro'])

    @patch('api.llm.gemini.genai')
    def test_create_chat_completion_text(self, mock_genai):
        # Mock model and chat
        mock_model = MagicMock()
        mock_chat = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.start_chat.return_value = mock_chat
        
        # Mock response
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = "Hello there"
        mock_part.function_call = None
        mock_response.parts = [mock_part]
        mock_chat.send_message.return_value = mock_response
        
        provider = GeminiProvider(api_key="test")
        messages = [
            {"role": "user", "content": "Hi"}
        ]
        
        response = provider.create_chat_completion(messages, "gemini-pro", tools=None, tool_choice=None)
        
        self.assertEqual(response.choices[0].message.content, "Hello there")
        self.assertIsNone(response.choices[0].message.tool_calls)
        
        # Verify call arguments
        mock_model.start_chat.assert_called()
        args, kwargs = mock_chat.send_message.call_args
        self.assertEqual(args[0], {'role': 'user', 'parts': [{'text': 'Hi'}]})

    @patch('api.llm.gemini.genai')
    def test_create_chat_completion_tool_call(self, mock_genai):
         # Mock model and chat
        mock_model = MagicMock()
        mock_chat = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.start_chat.return_value = mock_chat
        
        # Mock response with function call
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = None
        mock_part.function_call = SimpleNamespace(name="get_weather", args={'location': 'London'})
        mock_response.parts = [mock_part]
        
        mock_chat.send_message.return_value = mock_response
        
        provider = GeminiProvider(api_key="test")
        messages = [{"role": "user", "content": "Weather?"}]
        
        response = provider.create_chat_completion(messages, "gemini-pro", tools=[], tool_choice="auto")
        
        tool_calls = response.choices[0].message.tool_calls
        self.assertIsNotNone(tool_calls)
        self.assertEqual(tool_calls[0].function.name, "get_weather")
        self.assertEqual(json.loads(tool_calls[0].function.arguments), {'location': 'London'})

    @patch('api.llm.gemini.genai')
    def test_history_conversion_with_tools(self, mock_genai):
        mock_model = MagicMock()
        mock_chat = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.start_chat.return_value = mock_chat
        mock_chat.send_message.return_value = MagicMock(parts=[MagicMock(text="ok", function_call=None)])

        provider = GeminiProvider(api_key="test")
        messages = [
            {"role": "user", "content": "What's the weather?"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"function": {"name": "get_weather", "arguments": '{"location": "Paris"}'}}
            ]},
            {"role": "tool", "name": "get_weather", "content": '{"temp": 15}'} # Function response
        ]
        
        provider.create_chat_completion(messages, "gemini-pro", tools=[], tool_choice="auto")
        
        # Check start_chat history argument
        args, kwargs = mock_model.start_chat.call_args
        history = kwargs['history']
        
        # Item 0: User
        self.assertEqual(history[0]['role'], 'user')
        self.assertEqual(history[0]['parts'][0]['text'], "What's the weather?")
        
        # Item 1: Model (Assistant) calling function
        self.assertEqual(history[1]['role'], 'model')
        self.assertEqual(history[1]['parts'][0]['function_call']['name'], "get_weather")
        
        # Item 2: User (Function Response) - This is what we send as last message in this case?
        # WAIT. In my code:
        # last_message = gemini_history[-1]
        # history_except_last = gemini_history[:-1]
        # So start_chat gets 0 and 1. last_message is 2.
        
        # let's verify history length
        self.assertEqual(len(history), 2)
        
        # Verify the message sent is the function response
        msgs_args, msgs_kwargs = mock_chat.send_message.call_args
        sent_msg = msgs_args[0]
        self.assertEqual(sent_msg['role'], 'function')
        self.assertEqual(sent_msg['parts'][0]['function_response']['name'], 'get_weather')

if __name__ == '__main__':
    unittest.main()
