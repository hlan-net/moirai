import os
from .ollama import OllamaProvider
from .openai import OpenAIProvider

class LLMProviderFactory:
    def get_provider(self, llm_endpoint, api_key, ollama_base_url):
        if llm_endpoint == 'openai':
            return OpenAIProvider(api_key=api_key)
        else:
            return OllamaProvider(api_key='ollama', base_url=ollama_base_url)
