import re
import uuid
import json
from typing import AsyncIterator, List, Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.prompts import RAG_SYSTEM_PROMPT_V1, format_rag_user_prompt
from app.core.cache import CacheService
from app.repositories.document_repo import DocumentRepository
from app.services.llm.base import LLMProvider
from app.services.llm.factory import get_llm_provider
from app.models.chat import Conversation, Message


class RAGService:
    """
    Orchestrates vector similarity retrieval, citation extraction,
    and streaming grounded answers.
    """

    CITATION_REGEX = re.compile(r"\[\[doc:([^,]+),\s*page:(\d+),\s*chunk:(\d+)\]\]")

    @classmethod
    def parse_citations(cls, text: str) -> List[Dict[str, Any]]:
        """
        Extracts citation markers [[doc:filename, page:X, chunk:Y]] from response text.
        """
        citations = []
        seen = set()
        for match in cls.CITATION_REGEX.finditer(text):
            doc_name = match.group(1).strip()
            page = int(match.group(2))
            chunk_idx = int(match.group(3))
            key = (doc_name, page, chunk_idx)
            if key not in seen:
                seen.add(key)
                citations.append({
                    "document_name": doc_name,
                    "page": page,
                    "chunk_index": chunk_idx,
                })
        return citations

    @classmethod
    async def ask_question_stream(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        question: str,
        top_k: int = 5,
        provider: Optional[LLMProvider] = None,
    ) -> AsyncIterator[str]:
        """
        Core RAG generator:
        1. Checks Redis cache.
        2. Embeds question.
        3. Retrieves top-k similar chunks scoped to user_id.
        4. Streams answer token-by-token.
        5. Persists message & citations in PostgreSQL.
        6. Caches complete answer in Redis.
        """
        llm = provider or get_llm_provider()

        # 1. Check Redis cache
        cached_response = await CacheService.get_cached_rag_response(
            user_id=str(user_id),
            query=question
        )
        if cached_response:
            # Yield cached answer token by token (or chunked)
            answer = cached_response["answer"]
            yield f"data: {json.dumps({'token': answer, 'citations': cached_response.get('citations', [])})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 2. Embed user question
        question_embeddings = await llm.embed([question])
        if not question_embeddings:
            yield f"data: {json.dumps({'error': 'Failed to embed question.'})}\n\n"
            yield "data: [DONE]\n\n"
            return
        query_vector = question_embeddings[0]

        # 3. Retrieve similar chunks from pgvector
        results = await DocumentRepository.search_similar_chunks(
            db=db,
            user_id=user_id,
            query_vector=query_vector,
            top_k=top_k,
        )

        if not results:
            refusal_text = "Based on the provided documents, I do not have enough information to answer this question."
            yield f"data: {json.dumps({'token': refusal_text, 'citations': []})}\n\n"
            yield "data: [DONE]\n\n"
            # Persist message
            await cls._save_messages(db, conversation_id, question, refusal_text, citations=[])
            return

        # Prepare context blocks for prompt
        chunk_dicts = [
            {
                "filename": filename,
                "page": chunk.page,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
            }
            for chunk, filename, dist in results
        ]

        # 4. Format prompt
        user_prompt = format_rag_user_prompt(question=question, chunks=chunk_dicts)

        # 5. Stream tokens
        full_answer_tokens = []
        async for token in llm.stream(
            prompt=user_prompt,
            system_prompt=RAG_SYSTEM_PROMPT_V1,
            temperature=0.2,
        ):
            full_answer_tokens.append(token)
            payload = json.dumps({"token": token})
            yield f"data: {payload}\n\n"

        full_answer = "".join(full_answer_tokens)
        citations = cls.parse_citations(full_answer)

        # If model did not explicitly format markers, map top retrieved chunks as citations
        if not citations and "not have enough information" not in full_answer.lower():
            citations = [
                {"document_name": c["filename"], "page": c["page"], "chunk_index": c["chunk_index"]}
                for c in chunk_dicts[:3]
            ]

        # Yield completion packet with parsed citations
        done_payload = json.dumps({"done": True, "citations": citations})
        yield f"data: {done_payload}\n\n"
        yield "data: [DONE]\n\n"

        # 6. Persist user & assistant messages in PostgreSQL
        await cls._save_messages(db, conversation_id, question, full_answer, citations)

        # 7. Cache in Redis
        await CacheService.set_cached_rag_response(
            user_id=str(user_id),
            query=question,
            response_payload={"answer": full_answer, "citations": citations},
        )

    @staticmethod
    async def _save_messages(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        user_content: str,
        assistant_content: str,
        citations: List[dict]
    ) -> None:
        """Persists the turn into the messages table."""
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_content,
        )
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            citations=citations,
        )
        db.add(user_msg)
        db.add(assistant_msg)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
