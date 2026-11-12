from functools import lru_cache
from app.core.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.gemini import GeminiProvider
from app.services.llm.ollama import OllamaProvider

settings = get_settings()


@lru_cache()
def get_llm_provider() -> LLMProvider:
    """
    Returns the configured LLM provider instance based on settings.LLM_PROVIDER.
    Defaults to GeminiProvider with fallback to OllamaProvider.
    """
    provider_name = settings.LLM_PROVIDER.lower().strip()

    if provider_name == "ollama":
        return OllamaProvider()

    # Default to Gemini
    return GeminiProvider()
