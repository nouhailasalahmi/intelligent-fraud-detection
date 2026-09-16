import os
import requests 
from .base import LLM_Provider

class OllamaProvider(LLM_Provider):
    def __init__(self, model="llama3", base_url="http://localhost:11434/api/chat"):
        self.model = model
        url = base_url if base_url else "http://localhost:11434/api/chat"
        # Support pour conteneurs Docker accédant à l'hôte Windows
        if (os.path.exists("/.dockerenv") or os.getenv("IS_DOCKER") == "true") and ("localhost" in url or "127.0.0.1" in url):
            url = url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
            
        self.base_url = url if url.endswith("/api/chat") else url.rstrip("/") + "/api/chat"

    def generate(self, system_prompt: str, user_prompt: str) -> str: 
        response = requests.post(
            self.base_url,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "format": "json",
            }
        )
        response.raise_for_status()
        raw_text = response.json()["message"]["content"]  
        return raw_text

# Alias rétrocompatible
ollama_provider = OllamaProvider
