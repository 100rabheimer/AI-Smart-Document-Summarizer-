import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.user import User, UserSession


class UserRepository:
    """Data access layer for User and UserSession entities."""

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Fetch user by primary key UUID."""
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Fetch user by unique email."""
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_user(
        db: AsyncSession,
        email: str,
        name: str,
        avatar_url: Optional[str] = None
    ) -> User:
        """
        Idempotent insert or update (upsert) for OAuth logins.
        If user exists, update name and avatar; if not, create new user.
        """
        insert_stmt = insert(User).values(
            email=email,
            name=name,
            avatar_url=avatar_url,
            is_active=True,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[User.email],
            set_={
                "name": insert_stmt.excluded.name,
                "avatar_url": insert_stmt.excluded.avatar_url,
            }
        ).returning(User)

        result = await db.execute(upsert_stmt)
        await db.commit()
        return result.scalar_one()

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: uuid.UUID,
        session_token_hash: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> UserSession:
        """Create a new authenticated user session."""
        session = UserSession(
            user_id=user_id,
            session_token_hash=session_token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def get_active_session(
        db: AsyncSession,
        session_token_hash: str
    ) -> Optional[UserSession]:
        """Retrieve session by token hash if not expired and not revoked."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(UserSession)
            .where(
                UserSession.session_token_hash == session_token_hash,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke_session(
        db: AsyncSession,
        session_token_hash: str
    ) -> bool:
        """Revoke a session by marking revoked_at to current UTC time."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(UserSession)
            .where(
                UserSession.session_token_hash == session_token_hash,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
