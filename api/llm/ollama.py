from openai import OpenAI
from .base import LLMProvider

class OllamaProvider(LLMProvider):
    def __init__(self, api_key, base_url):
        # Set generous timeout for slow local Ollama (5 minutes)
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=300.0)

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
