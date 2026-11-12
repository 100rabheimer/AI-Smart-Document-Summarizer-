from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional


class LLMProvider(ABC):
    """
    Abstract Base Class defining the unified interface for all LLM providers.
    Decouples DocMind from any single vendor SDK.
    """

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generates vector embeddings for a batch of text chunks.
        Guarantees embedding dimension matches project configuration (e.g. 768).
        """
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        **kwargs
    ) -> str:
        """
        Synchronous-style non-streaming text generation.
        Returns complete model response.
        """
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Asynchronous generator yielding tokens in real-time as they are produced.
        """
        pass
