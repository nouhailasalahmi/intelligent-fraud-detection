from abc import ABC, abstractmethod

class LLM_Provider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        pass

# Alias pour supporter la casse PascalCase
LLMProvider = LLM_Provider