from .ollama import OllamaProvider
from .openai import OpenAIProvider

def get_llm_provider(llm_endpoint, api_key, base_url):
    if llm_endpoint == 'openai':
        return OpenAIProvider(api_key=api_key)
    else:
        return OllamaProvider(api_key=api_key, base_url=base_url)
