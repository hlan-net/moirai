from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def list_models(self):
        pass

    @abstractmethod
    def create_chat_completion(self, messages, model, tools, tool_choice):
        pass
