from .base import LLMProvider


class MistralProvider(LLMProvider):
    """Fournisseur pour modèles Mistral AI (Mistral Large, Mistral Small, etc.)."""
    
    def __init__(self, api_key: str = None, model="mistral-large-latest"):
        from mistralai import Mistral
        self.client = Mistral(api_key=api_key)
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.complete(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content


mistral_provider = MistralProvider
