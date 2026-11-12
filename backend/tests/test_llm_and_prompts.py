import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.core.prompts import format_rag_user_prompt, RAG_SYSTEM_PROMPT_V1
from app.services.llm.gemini import GeminiProvider
from app.services.llm.ollama import OllamaProvider
from app.services.summary_service import SummaryService
from app.schemas.document import DocumentSummary


def test_format_rag_user_prompt():
    """Verify that chunks are formatted safely inside XML delimiters with metadata."""
    chunks = [
        {"filename": "contract.pdf", "page": 3, "chunk_index": 5, "content": "The agreement terminates on June 30."},
        {"filename": "notes.md", "page": 1, "chunk_index": 1, "content": "Renewal requires 30 days notice."},
    ]
    prompt = format_rag_user_prompt(question="When does it terminate?", chunks=chunks)

    assert "<document_context>" in prompt
    assert "</document_context>" in prompt
    assert 'doc="contract.pdf"' in prompt
    assert 'page="3"' in prompt
    assert 'The agreement terminates on June 30.' in prompt
    assert "User Question: When does it terminate?" in prompt


@pytest.mark.asyncio
async def test_gemini_provider_generate():
    """Verify GeminiProvider parses generateContent API responses correctly."""
    provider = GeminiProvider(api_key="fake-key", chat_model="gemini-1.5-flash")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "DocMind is an AI assistant."}]
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        output = await provider.generate("Tell me about DocMind")
        assert output == "DocMind is an AI assistant."


@pytest.mark.asyncio
async def test_gemini_provider_embed():
    """Verify GeminiProvider parses batchEmbedContents API responses correctly."""
    provider = GeminiProvider(api_key="fake-key", embedding_model="models/text-embedding-004")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "embeddings": [
            {"values": [0.1, 0.2, 0.3]},
            {"values": [-0.1, -0.2, -0.3]},
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        vectors = await provider.embed(["chunk 1", "chunk 2"])
        assert len(vectors) == 2
        assert vectors[0] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_ollama_provider_generate():
    """Verify OllamaProvider calls /api/generate and returns response field."""
    provider = OllamaProvider(base_url="http://localhost:11434", chat_model="llama3")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "Local response from Ollama."}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await provider.generate("Hello local model")
        assert res == "Local response from Ollama."


@pytest.mark.asyncio
async def test_summary_service_success():
    """Verify SummaryService parses valid JSON into a Pydantic DocumentSummary."""
    raw_llm_json = """{
        "title": "Quarterly Financial Report",
        "summary": "Revenue increased by 15% due to cloud growth. Operating margins improved.",
        "key_points": ["Revenue up 15%", "Operating margin at 24%", "Guidance raised"],
        "topics": ["Finance", "Cloud", "Earnings"]
    }"""

    mock_provider = AsyncMock()
    mock_provider.generate.return_value = raw_llm_json

    summary: DocumentSummary = await SummaryService.generate_summary(
        document_text="financial text content...",
        provider=mock_provider
    )

    assert summary.title == "Quarterly Financial Report"
    assert len(summary.key_points) == 3
    assert "Finance" in summary.topics


@pytest.mark.asyncio
async def test_summary_service_strips_code_fences():
    """Verify SummaryService handles LLM output wrapped in markdown code blocks."""
    raw_llm_markdown = """```json
    {
        "title": "Architecture Guide",
        "summary": "Covers backend layered pattern.",
        "key_points": ["FastAPI", "PostgreSQL", "Redis"],
        "topics": ["Architecture", "Engineering"]
    }
    ```"""

    mock_provider = AsyncMock()
    mock_provider.generate.return_value = raw_llm_markdown

    summary: DocumentSummary = await SummaryService.generate_summary(
        document_text="guide text...",
        provider=mock_provider
    )

    assert summary.title == "Architecture Guide"
    assert summary.key_points == ["FastAPI", "PostgreSQL", "Redis"]


@pytest.mark.asyncio
async def test_summary_service_invalid_json():
    """Verify SummaryService raises ValueError when LLM output violates schema."""
    malformed_output = "I cannot summarize this document."

    mock_provider = AsyncMock()
    mock_provider.generate.return_value = malformed_output

    with pytest.raises(ValueError) as exc_info:
        await SummaryService.generate_summary(
            document_text="content...",
            provider=mock_provider
        )
    assert "invalid structured summary JSON" in str(exc_info.value)
