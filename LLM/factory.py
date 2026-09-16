import os
try:
    import config
except ImportError:
    config = None

from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .mistral_provider import MistralProvider

def get_llm_provider():
    default_provider = getattr(config, "LLM_PROVIDER", "ollama") if config else "ollama"
    provider_name = os.getenv("LLM_PROVIDER", default_provider).lower()

    if provider_name == "ollama":
        model = getattr(config, "OLLAMA_MODEL", "llama3:latest") if config else os.getenv("OLLAMA_MODEL", "llama3:latest")
        base_url = getattr(config, "OLLAMA_BASE_URL", "http://localhost:11434") if config else os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return OllamaProvider(model=model, base_url=base_url)
    elif provider_name == "openai":
        return OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))
    elif provider_name == "anthropic":
        return AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif provider_name == "mistral":
        return MistralProvider(api_key=os.getenv("MISTRAL_API_KEY"))
    else:
        raise ValueError(f"Provider inconnu : {provider_name}")