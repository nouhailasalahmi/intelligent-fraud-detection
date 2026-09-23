from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """Fournisseur pour modèles OpenAI (GPT-4o, GPT-4o-mini, etc.)."""
    
    def __init__(self, api_key: str = None, model="gpt-4o"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content


openai_provider = OpenAIProvider
