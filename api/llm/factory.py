from .aisa import AisaProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider


class LLMProviderFactory:
    def get_provider(self, llm_endpoint, api_key, ollama_base_url):
        if llm_endpoint == "openai":
            return OpenAIProvider(api_key=api_key)
        elif llm_endpoint == "gemini":
            return GeminiProvider(api_key=api_key)
        elif llm_endpoint == "aisa":
            # In-cluster AISA proxy: credentials come from the environment
            # (AISA-managed Secret), never from the userspace document.
            return AisaProvider.from_env()
        else:
            return OllamaProvider(api_key="ollama", base_url=ollama_base_url)
