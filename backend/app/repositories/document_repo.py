import uuid
from typing import List, Optional, Tuple, Any
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, Chunk


class DocumentRepository:
    """Data access layer for Document and Chunk entities."""

    @staticmethod
    async def create_document(
        db: AsyncSession,
        user_id: uuid.UUID,
        filename: str,
        content_hash: str,
        mime_type: str,
        size: int,
        storage_path: str,
        status: str = "uploaded",
    ) -> Document:
        """Creates a document record with uploaded status."""
        doc = Document(
            user_id=user_id,
            filename=filename,
            content_hash=content_hash,
            mime_type=mime_type,
            size=size,
            storage_path=storage_path,
            status=status,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        document_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[Document]:
        """Fetches document by ID strictly scoped to user_id."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_content_hash(
        db: AsyncSession,
        user_id: uuid.UUID,
        content_hash: str,
    ) -> Optional[Document]:
        """Checks if identical file already exists for this user."""
        stmt = select(Document).where(
            Document.user_id == user_id,
            Document.content_hash == content_hash,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 50,
        status_filter: Optional[str] = None,
    ) -> List[Document]:
        """Lists user documents with optional status filtering."""
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        if status_filter:
            stmt = stmt.where(Document.status == status_filter)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        db: AsyncSession,
        document_id: uuid.UUID,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """Updates processing status (uploaded -> processing -> ready / failed)."""
        stmt = (
            update(Document)
            .where(Document.id == document_id)
            .values(status=status, error=error)
        )
        await db.execute(stmt)
        await db.commit()

    @staticmethod
    async def delete_document(
        db: AsyncSession,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Deletes a document and its cascading chunks."""
        stmt = (
            delete(Document)
            .where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def create_chunks_batch(
        db: AsyncSession,
        chunks_data: List[dict]
    ) -> None:
        """Bulk inserts chunks and vector embeddings in a single transaction."""
        if not chunks_data:
            return

        chunks = [
            Chunk(
                document_id=c["document_id"],
                user_id=c["user_id"],
                chunk_index=c["chunk_index"],
                page=c.get("page"),
                content=c["content"],
                embedding=c["embedding"],
            )
            for c in chunks_data
        ]
        db.add_all(chunks)
        await db.commit()

    @staticmethod
    async def search_similar_chunks(
        db: AsyncSession,
        user_id: uuid.UUID,
        query_vector: List[float],
        top_k: int = 5,
        document_id: Optional[uuid.UUID] = None,
    ) -> List[Tuple[Chunk, str, float]]:
        """
        Multi-tenant vector similarity search via pgvector cosine distance (<=>).
        Returns list of (Chunk, filename, distance) tuples.
        """
        # Cosine distance expression using pgvector
        cosine_dist = Chunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(Chunk, Document.filename, cosine_dist.label("distance"))
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.user_id == user_id)
        )

        if document_id:
            stmt = stmt.where(Chunk.document_id == document_id)

        stmt = stmt.order_by(cosine_dist).limit(top_k)

        result = await db.execute(stmt)
        return [(row[0], row[1], float(row[2])) for row in result.all()]
