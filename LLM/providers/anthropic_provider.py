from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Fournisseur pour modèles Anthropic Claude (Claude 3.5 Sonnet, Claude 3 Opus, etc.)."""
    
    def __init__(self, api_key: str = None, model="claude-3-5-sonnet-20241022"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.content[0].text


anthropic_provider = AnthropicProvider
