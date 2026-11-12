import os
import uuid
import hashlib
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.cache import CacheService
from app.core.database import AsyncSessionLocal
from app.repositories.document_repo import DocumentRepository
from app.services.document_parser import DocumentParser, TextChunk
from app.services.llm.base import LLMProvider
from app.services.llm.factory import get_llm_provider
from app.models.document import Document

settings = get_settings()


class DocumentService:
    """Service orchestrating document upload, background extraction, and vector indexing."""

    @staticmethod
    def compute_hash(file_bytes: bytes) -> str:
        """Computes SHA-256 hash of file content."""
        return hashlib.sha256(file_bytes).hexdigest()

    @classmethod
    async def upload_document(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
    ) -> Tuple[Document, bool]:
        """
        Validates and stores uploaded document record.
        Returns: (Document, is_duplicate)
        """
        # Validate file size
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValueError(f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.")

        content_hash = cls.compute_hash(file_bytes)

        # Check for content hash duplicate for this tenant
        existing = await DocumentRepository.get_by_content_hash(
            db=db,
            user_id=user_id,
            content_hash=content_hash,
        )
        if existing:
            return existing, True

        # Ensure storage directory exists
        os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)
        storage_filename = f"{user_id}_{content_hash}_{filename}"
        storage_path = os.path.join(settings.LOCAL_STORAGE_DIR, storage_filename)

        # Save to local disk
        with open(storage_path, "wb") as f:
            f.write(file_bytes)

        # Create database record
        doc = await DocumentRepository.create_document(
            db=db,
            user_id=user_id,
            filename=filename,
            content_hash=content_hash,
            mime_type=mime_type,
            size=len(file_bytes),
            storage_path=storage_path,
            status="uploaded",
        )

        return doc, False

    @classmethod
    async def process_document_background(
        cls,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        storage_path: str,
        filename: str,
        provider: Optional[LLMProvider] = None,
    ) -> None:
        """
        Background task:
        1. Reads file bytes.
        2. Extracts text pages (PDF/TXT/MD).
        3. Chunks text with overlap.
        4. Generates batch vector embeddings via LLMProvider.
        5. Bulk-inserts into PostgreSQL pgvector chunks table.
        6. Invalidates user's Redis query cache by bumping docs_version.
        7. Updates document status to 'ready' (or 'failed').
        """
        llm = provider or get_llm_provider()

        async with AsyncSessionLocal() as db:
            try:
                await DocumentRepository.update_status(db, document_id, status="processing")

                # 1. Read file
                with open(storage_path, "rb") as f:
                    file_bytes = f.read()

                # 2. Extract pages
                pages = DocumentParser.extract_text(file_bytes=file_bytes, filename=filename)
                if not pages:
                    raise ValueError("Document contains no readable text.")

                # 3. Create overlapping chunks
                chunks: List[TextChunk] = DocumentParser.chunk_document(pages)
                if not chunks:
                    raise ValueError("No text chunks could be produced from document.")

                # 4. Generate batch embeddings
                texts = [c.content for c in chunks]
                embeddings = await llm.embed(texts)

                # 5. Prepare bulk insert payload
                chunk_records = []
                for chunk, embedding in zip(chunks, embeddings):
                    chunk_records.append({
                        "document_id": document_id,
                        "user_id": user_id,
                        "chunk_index": chunk.chunk_index,
                        "page": chunk.page,
                        "content": chunk.content,
                        "embedding": embedding,
                    })

                await DocumentRepository.create_chunks_batch(db, chunk_records)

                # 6. Increment docs_version in Redis (O(1) cache invalidation)
                await CacheService.invalidate_user_docs_cache(user_id=str(user_id))

                # 7. Mark ready
                await DocumentRepository.update_status(db, document_id, status="ready")

            except Exception as exc:
                error_msg = str(exc)
                await DocumentRepository.update_status(
                    db,
                    document_id=document_id,
                    status="failed",
                    error=error_msg[:1000],
                )
