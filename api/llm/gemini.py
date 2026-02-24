from google import genai
from google.genai import types
import json
from types import SimpleNamespace
from .base import LLMProvider

import logging

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.api_key = api_key

    def list_models(self):
        try:
            models = self.client.models.list()
            # Filter for models that support generation
            return [
                m.name.replace("models/", "")
                for m in models
                if "generateContent" in m.supported_generation_methods
            ]
        except Exception as e:
            logger.error(f"Error listing Gemini models: {e}")
            raise e

    def create_chat_completion(self, messages, model, tools, tool_choice):
        # 1. Setup Config
        system_instruction = None
        # Extract system prompt if present
        if messages and messages[0]["role"] == "system":
            system_instruction = messages[0]["content"]
            messages = messages[1:]

        gemini_tools = self._convert_tools(tools)
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=gemini_tools,
        )

        # 2. Convert History
        gemini_contents = self._convert_history(messages)

        if not gemini_contents:
            return self._mock_response("No messages provided.")

        # 3. Generate Content
        try:
            model_id = model if model.startswith("models/") else f"models/{model}"
            response = self.client.models.generate_content(
                model=model_id,
                contents=gemini_contents,
                config=config
            )
            return self._convert_response(response)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._mock_response(f"Gemini API error: {str(e)}")

    def _convert_tools(self, tools):
        if not tools:
            return None

        function_declarations = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                function_declarations.append(
                    types.FunctionDeclaration(
                        name=func["name"],
                        description=func.get("description"),
                        parameters=func.get("parameters"),
                    )
                )
        
        if not function_declarations:
            return None
            
        return [types.Tool(function_declarations=function_declarations)]

    def _convert_history(self, messages):
        gemini_history = []
        for msg in messages:
            gemini_msg = self._convert_message_to_gemini(msg)
            if gemini_msg:
                gemini_history.append(gemini_msg)
        return gemini_history

    def _convert_message_to_gemini(self, msg):
        role = msg["role"]
        content = msg.get("content")

        if role == "user":
            return self._convert_user_message(content)
        elif role == "assistant":
            return self._convert_assistant_message(msg, content)
        elif role == "tool":
            return self._convert_tool_message(msg, content)

        return None

    def _convert_user_message(self, content):
        parts = [types.Part(text=content)] if content else []
        return types.Content(role="user", parts=parts)

    def _convert_assistant_message(self, msg, content):
        parts = []
        if content:
            parts.append(types.Part(text=content))

        # Handle tool calls
        if "tool_calls" in msg and msg["tool_calls"]:
            for tc in msg["tool_calls"]:
                parts.append(self._convert_tool_call(tc))

        return types.Content(role="model", parts=parts)

    def _convert_tool_call(self, tc):
        if isinstance(tc, dict):
            func = tc["function"]
            func_name = func["name"]
            func_args = json.loads(func["arguments"])
        else:
            # SimpleNamespace (mock or from previous turn)
            func = tc.function
            func_name = func.name
            func_args = json.loads(func.arguments)

        return types.Part(
            function_call=types.FunctionCall(
                name=func_name,
                args=func_args
            )
        )

    def _convert_tool_message(self, msg, content):
        # FunctionResponse part
        return types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name=msg["name"],
                        response={"result": content},
                    )
                )
            ]
        )

    def _convert_response(self, response):
        # Convert Gemini response to OpenAI-like object
        content = None
        tool_calls = []

        if not response.candidates:
            return self._mock_response("No candidates in response")

        for part in response.candidates[0].content.parts:
            if part.text:
                content = (content or "") + part.text

            if part.function_call:
                tool_calls.append(self._map_function_call(part.function_call))

        # Create message object
        message = SimpleNamespace(
            role="assistant",
            content=content,
            tool_calls=tool_calls if tool_calls else None,
        )

        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    def _map_function_call(self, fc):
        return SimpleNamespace(
            id=f"call_{fc.name}",
            type="function",
            function=SimpleNamespace(
                name=fc.name,
                arguments=json.dumps(dict(fc.args) if fc.args else {}),
            ),
        )

    def _mock_response(self, text):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        role="assistant", content=text, tool_calls=None
                    )
                )
            ]
        )
