import json
from typing import AsyncIterator, List, Optional
import httpx

from app.core.config import get_settings
from app.services.llm.base import LLMProvider

settings = get_settings()

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    """
    Google Gemini implementation using high-performance async HTTP/SSE requests.
    Supports Gemini 1.5/2.0 Flash chat and text-embedding-004.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        chat_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.chat_model = chat_model or settings.CHAT_MODEL
        # Normalize embedding model path (e.g. text-embedding-004 -> models/text-embedding-004)
        emb_model = embedding_model or settings.EMBEDDING_MODEL
        self.embedding_model = emb_model if emb_model.startswith("models/") else f"models/{emb_model}"

    def _get_model_id(self, model: str) -> str:
        """Strips models/ prefix if present for URL path."""
        return model.replace("models/", "")

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generates vector embeddings for a batch of text chunks using batchEmbedContents.
        """
        if not texts:
            return []

        model_id = self._get_model_id(self.embedding_model)
        url = f"{GEMINI_API_BASE}/models/{model_id}:batchEmbedContents?key={self.api_key}"

        requests_payload = [
            {
                "model": self.embedding_model,
                "content": {"parts": [{"text": text}]},
            }
            for text in texts
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json={"requests": requests_payload})
            if response.status_code != 200:
                raise RuntimeError(f"Gemini embedding API failed ({response.status_code}): {response.text}")

            data = response.json()
            embeddings = [item["values"] for item in data.get("embeddings", [])]
            return embeddings

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        **kwargs
    ) -> str:
        """Non-streaming generation."""
        model_id = self._get_model_id(self.chat_model)
        url = f"{GEMINI_API_BASE}/models/{model_id}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise RuntimeError(f"Gemini generate API failed ({response.status_code}): {response.text}")

            data = response.json()
            try:
                candidate = data["candidates"][0]
                text = candidate["content"]["parts"][0]["text"]
                return text
            except (KeyError, IndexError) as err:
                raise RuntimeError(f"Unexpected Gemini response structure: {data}") from err

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Streaming generation via Server-Sent Events (SSE).
        Yields tokens incrementally as they arrive.
        """
        model_id = self._get_model_id(self.chat_model)
        url = f"{GEMINI_API_BASE}/models/{model_id}:streamGenerateContent?alt=sse&key={self.api_key}"

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise RuntimeError(f"Gemini stream API failed ({response.status_code}): {error_body.decode()}")

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue

                    json_str = line[len("data: "):]
                    try:
                        chunk = json.loads(json_str)
                        parts = chunk["candidates"][0]["content"]["parts"]
                        token = "".join(part.get("text", "") for part in parts)
                        if token:
                            yield token
                    except Exception:
                        continue
