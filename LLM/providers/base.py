from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Classe abstraite de base pour tous les fournisseurs de modèles LLM."""
    
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Génère une réponse textuelle à partir d'un prompt système et utilisateur."""
        pass


# Alias rétrocompatible
LLM_Provider = LLMProvider
