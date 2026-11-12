import uuid
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.document_parser import DocumentParser, ParsedPage
from app.services.rag_service import RAGService
from app.services.document_service import DocumentService
from app.models.document import Document, Chunk


def test_document_parser_plain_text():
    """Verify text extraction from plain text and markdown bytes."""
    sample_text = "# Title\n\nDocMind architecture overview."
    pages = DocumentParser.extract_text(sample_text.encode("utf-8"), "overview.md")
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "DocMind architecture overview." in pages[0].text


def test_document_parser_chunking_with_overlap():
    """Verify that chunking creates overlapping text fragments and sequential indices."""
    long_text = "Paragraph One.\n\n" * 20
    pages = [ParsedPage(text=long_text, page_number=1)]

    chunks = DocumentParser.chunk_document(pages, chunk_size=100, chunk_overlap=30)
    assert len(chunks) > 1
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[0].page == 1


def test_rag_citation_parser():
    """Verify regex extraction of citations from LLM answer."""
    text = (
        "The policy renewal deadline is December 15 [[doc:policy.pdf, page:3, chunk:4]]. "
        "Late fees are waived for first-time offenders [[doc:policy.pdf, page:3, chunk:5]]."
    )
    citations = RAGService.parse_citations(text)
    assert len(citations) == 2
    assert citations[0]["document_name"] == "policy.pdf"
    assert citations[0]["page"] == 3
    assert citations[0]["chunk_index"] == 4
    assert citations[1]["chunk_index"] == 5


@pytest.mark.asyncio
async def test_document_upload_duplicate_detection():
    """Verify that uploading the exact same file content detects duplicate and skips re-upload."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    file_bytes = b"Sample unique document content"
    content_hash = DocumentService.compute_hash(file_bytes)

    existing_doc = Document(
        id=uuid.uuid4(),
        user_id=user_id,
        filename="existing.txt",
        content_hash=content_hash,
        size=len(file_bytes),
        storage_path="/tmp/existing.txt",
        status="ready",
    )

    with patch("app.repositories.document_repo.DocumentRepository.get_by_content_hash", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = existing_doc
        doc, is_duplicate = await DocumentService.upload_document(
            db=mock_db,
            user_id=user_id,
            filename="new_name.txt",
            file_bytes=file_bytes,
            mime_type="text/plain",
        )
        assert is_duplicate is True
        assert doc.id == existing_doc.id


@pytest.mark.asyncio
async def test_rag_service_refusal_when_no_chunks():
    """Verify RAGService returns explicit refusal when no document chunks match."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    mock_provider = AsyncMock()
    mock_provider.embed.return_value = [[0.1] * 768]

    with patch("app.core.cache.CacheService.get_cached_rag_response", new_callable=AsyncMock) as mock_cache, \
         patch("app.repositories.document_repo.DocumentRepository.search_similar_chunks", new_callable=AsyncMock) as mock_search, \
         patch("app.services.rag_service.RAGService._save_messages", new_callable=AsyncMock):

        mock_cache.return_value = None
        mock_search.return_value = []  # No chunks retrieved

        events = []
        async for chunk in RAGService.ask_question_stream(
            db=mock_db,
            user_id=user_id,
            conversation_id=conv_id,
            question="What is the CEO salary?",
            provider=mock_provider,
        ):
            events.append(chunk)

        full_output = "".join(events)
        assert "not have enough information" in full_output
        assert "[DONE]" in full_output


@pytest.mark.asyncio
async def test_rag_service_streaming_and_citations():
    """Verify RAGService streams tokens and attaches citations."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    mock_provider = AsyncMock()
    mock_provider.embed.return_value = [[0.2] * 768]

    # Generator for mock streaming tokens
    async def mock_stream_tokens(*args, **kwargs):
        tokens = [
            "The ", "deadline ", "is ", "June ", "30 ",
            "[[doc:agreement.pdf, page:1, chunk:2]]."
        ]
        for t in tokens:
            yield t

    mock_provider.stream = mock_stream_tokens

    dummy_chunk = Chunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        user_id=user_id,
        chunk_index=2,
        page=1,
        content="The deadline is June 30.",
        embedding=[0.2] * 768,
    )

    with patch("app.core.cache.CacheService.get_cached_rag_response", new_callable=AsyncMock) as mock_cache, \
         patch("app.core.cache.CacheService.set_cached_rag_response", new_callable=AsyncMock), \
         patch("app.repositories.document_repo.DocumentRepository.search_similar_chunks", new_callable=AsyncMock) as mock_search, \
         patch("app.services.rag_service.RAGService._save_messages", new_callable=AsyncMock):

        mock_cache.return_value = None
        mock_search.return_value = [(dummy_chunk, "agreement.pdf", 0.05)]

        streamed_chunks = []
        async for packet in RAGService.ask_question_stream(
            db=mock_db,
            user_id=user_id,
            conversation_id=conv_id,
            question="When is the deadline?",
            provider=mock_provider,
        ):
            streamed_chunks.append(packet)

        raw_stream = "".join(streamed_chunks)
        assert "agreement.pdf" in raw_stream
        assert "June" in raw_stream
        assert "30" in raw_stream
        assert "[DONE]" in raw_stream
