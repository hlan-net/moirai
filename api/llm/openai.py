from openai import OpenAI
from .base import LLMProvider

OPENAI_TIMEOUT_SECONDS = 120.0

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key):
        # Explicit timeout for OpenAI API
        self.client = OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT_SECONDS)

    def list_models(self):
        models_response = self.client.models.list()
        return [m.id for m in models_response.data]

    def create_chat_completion(self, messages, model, tools, tool_choice):
        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice
        )
