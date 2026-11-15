"""
Memory Repository — Phase 6, Layer 3

Handles database access for:
  1. Short-term memory: Recent conversation turns scoped to conversation & user_id.
  2. Long-term memory: Key-value preferences/facts in the user_memories table.
"""

from __future__ import annotations

import uuid
from typing import Optional, Sequence
from datetime import datetime, timezone

from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.chat import Conversation, Message
from app.models.memory import UserMemory


class MemoryRepository:
    """Data access layer for conversational history and user memories."""

    @staticmethod
    async def get_recent_messages(
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        limit: int = 10,
    ) -> Sequence[Message]:
        """
        Fetch the last `limit` messages for a conversation, verifying user ownership.
        Returns messages in chronological order (oldest to newest).
        """
        # Ensure the conversation belongs to the authenticated user
        conv_stmt = select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        conv_res = await db.execute(conv_stmt)
        if not conv_res.scalar_one_or_none():
            return []

        # Retrieve the latest `limit` messages ordered by created_at DESC
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        result = await db.execute(stmt)
        messages = result.scalars().all()

        # Reverse so they read chronologically (oldest -> newest)
        return list(reversed(messages))

    @staticmethod
    async def get_memory(
        db: AsyncSession,
        user_id: uuid.UUID,
        key: str,
    ) -> Optional[UserMemory]:
        """Fetch a single user memory by user_id and key."""
        stmt = select(UserMemory).where(
            UserMemory.user_id == user_id,
            UserMemory.key == key,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_memories(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Sequence[UserMemory]:
        """Fetch all stored memories/preferences for a user."""
        stmt = (
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .order_by(UserMemory.key)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def upsert_memory(
        db: AsyncSession,
        user_id: uuid.UUID,
        key: str,
        value: str,
    ) -> UserMemory:
        """
        Idempotent insert or update (upsert) for a user memory key-value pair.
        """
        now = datetime.now(timezone.utc)
        insert_stmt = insert(UserMemory).values(
            user_id=user_id,
            key=key,
            value=value,
            updated_at=now,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["user_id", "key"],
            set_={
                "value": insert_stmt.excluded.value,
                "updated_at": now,
            },
        ).returning(UserMemory)

        result = await db.execute(upsert_stmt)
        await db.commit()
        return result.scalar_one()

    @staticmethod
    async def delete_memory(
        db: AsyncSession,
        user_id: uuid.UUID,
        key: str,
    ) -> bool:
        """Delete a user memory item. Returns True if deleted, False if not found."""
        stmt = delete(UserMemory).where(
            UserMemory.user_id == user_id,
            UserMemory.key == key,
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
