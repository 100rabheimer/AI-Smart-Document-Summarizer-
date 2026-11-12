import json
from typing import AsyncIterator, List, Optional
import httpx

from app.core.config import get_settings
from app.services.llm.base import LLMProvider

settings = get_settings()


class OllamaProvider(LLMProvider):
    """
    Local Ollama implementation for offline development and local inference.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        chat_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        self.base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.chat_model = chat_model or "llama3"
        self.embedding_model = embedding_model or "nomic-embed-text"

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding generation via Ollama /api/embed."""
        if not texts:
            return []

        url = f"{self.base_url}/api/embed"
        payload = {"model": self.embedding_model, "input": texts}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                # Fallback to single-item /api/embeddings endpoint if legacy version
                return await self._legacy_embed(texts, client)

            data = response.json()
            return data.get("embeddings", [])

    async def _legacy_embed(self, texts: List[str], client: httpx.AsyncClient) -> List[List[float]]:
        """Fallback for older Ollama versions supporting only /api/embeddings."""
        url = f"{self.base_url}/api/embeddings"
        embeddings = []
        for text in texts:
            res = await client.post(url, json={"model": self.embedding_model, "prompt": text})
            if res.status_code != 200:
                raise RuntimeError(f"Ollama embedding failed ({res.status_code}): {res.text}")
            embeddings.append(res.json()["embedding"])
        return embeddings

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        **kwargs
    ) -> str:
        """Non-streaming generation via Ollama /api/generate."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.chat_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise RuntimeError(f"Ollama generate failed ({response.status_code}): {response.text}")
            return response.json().get("response", "")

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        **kwargs
    ) -> AsyncIterator[str]:
        """Streaming generation via Ollama /api/generate."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.chat_model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err = await response.aread()
                    raise RuntimeError(f"Ollama stream failed ({response.status_code}): {err.decode()}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done", False):
                            break
                    except Exception:
                        continue
