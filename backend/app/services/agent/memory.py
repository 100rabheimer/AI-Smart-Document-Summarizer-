"""
Memory Service — Phase 6, Layer 3

Orchestrates short-term conversational context and long-term user preferences
for seamless injection into the ReAct Agent prompt.
"""

from __future__ import annotations

import uuid
from typing import Sequence, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import UserMemory
from app.repositories.memory_repo import MemoryRepository


class MemoryService:
    """Service layer for multi-tier agent memory management."""

    def __init__(self, repo: type[MemoryRepository] = MemoryRepository) -> None:
        self.repo = repo

    async def get_short_term_context(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        limit: int = 6,
    ) -> str:
        """
        Retrieves recent turns from the conversation and formats them
        as a compact dialogue buffer.
        """
        messages = await self.repo.get_recent_messages(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=limit,
        )
        if not messages:
            return ""

        buffer_lines: list[str] = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            # Keep each message turn concise in context
            content_snippet = msg.content.strip()
            buffer_lines.append(f"{role_label}: {content_snippet}")

        return "\n".join(buffer_lines)

    async def get_long_term_context(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> str:
        """
        Retrieves all user memories/preferences and formats them
        into an XML-delimited instruction block.
        """
        memories = await self.repo.list_memories(db=db, user_id=user_id)
        if not memories:
            return ""

        pref_lines: list[str] = ["<user_preferences>"]
        for mem in memories:
            pref_lines.append(f"  - {mem.key}: {mem.value}")
        pref_lines.append("</user_preferences>")

        return "\n".join(pref_lines)

    async def assemble_agent_context(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
        short_term_limit: int = 6,
    ) -> str:
        """
        Combines long-term preferences and short-term conversation context
        into a unified context string for the ReAct agent loop.
        """
        sections: list[str] = []

        # 1. Long-term user preferences
        long_term = await self.get_long_term_context(db=db, user_id=user_id)
        if long_term:
            sections.append(long_term)

        # 2. Short-term dialogue context (if active conversation)
        if conversation_id:
            short_term = await self.get_short_term_context(
                db=db,
                user_id=user_id,
                conversation_id=conversation_id,
                limit=short_term_limit,
            )
            if short_term:
                sections.append(f"<conversation_history>\n{short_term}\n</conversation_history>")

        return "\n\n".join(sections)

    async def set_user_preference(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        key: str,
        value: str,
    ) -> UserMemory:
        """Saves or updates a user preference in long-term memory."""
        cleaned_key = key.strip().lower()
        cleaned_value = value.strip()
        return await self.repo.upsert_memory(
            db=db,
            user_id=user_id,
            key=cleaned_key,
            value=cleaned_value,
        )

    async def list_user_preferences(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Sequence[UserMemory]:
        """Lists all user preferences for the current tenant."""
        return await self.repo.list_memories(db=db, user_id=user_id)

    async def delete_user_preference(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        key: str,
    ) -> bool:
        """Removes a user preference from long-term memory."""
        return await self.repo.delete_memory(db=db, user_id=user_id, key=key.strip().lower())
