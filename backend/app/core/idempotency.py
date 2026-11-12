import json
import uuid
from typing import Optional, Tuple, Any
from fastapi import Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.redis import redis_client
from app.models.idempotency import IdempotencyKey

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
IDEMPOTENCY_TTL_SECONDS = 86400  # 24 hours


class IdempotencyService:
    """
    Manages request deduplication via Redis cache and PostgreSQL backup.
    Guarantees mutative operations (like document uploads) are executed at most once.
    """

    @staticmethod
    def get_key_from_request(request: Request) -> Optional[str]:
        """Extracts Idempotency-Key header from incoming HTTP request."""
        return request.headers.get(IDEMPOTENCY_KEY_HEADER)

    @classmethod
    async def get_cached_response(
        cls,
        user_id: uuid.UUID,
        key: str,
        db: Optional[AsyncSession] = None,
        client: Optional[Redis] = None,
    ) -> Optional[Tuple[int, Any]]:
        """
        Looks up existing response for an idempotency key.
        1. Fast path: Redis cache
        2. Slow path: PostgreSQL database
        """
        r = client or redis_client
        redis_key = f"idemp:{str(user_id)}:{key}"

        # 1. Fast path: Redis
        cached = await r.get(redis_key)
        if cached:
            try:
                data = json.loads(cached)
                return data["status_code"], data["body"]
            except Exception:
                pass

        # 2. Database fallback
        if db:
            stmt = select(IdempotencyKey).where(
                IdempotencyKey.key == key,
                IdempotencyKey.user_id == user_id,
            )
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            if record:
                # Repopulate Redis cache
                await r.set(
                    redis_key,
                    json.dumps({"status_code": record.response_code, "body": record.response_body}),
                    ex=IDEMPOTENCY_TTL_SECONDS,
                )
                return record.response_code, record.response_body

        return None

    @classmethod
    async def record_response(
        cls,
        user_id: uuid.UUID,
        key: str,
        request_hash: str,
        status_code: int,
        response_body: Any,
        db: Optional[AsyncSession] = None,
        client: Optional[Redis] = None,
    ) -> None:
        """
        Stores response in Redis with TTL and persists in PostgreSQL.
        """
        r = client or redis_client
        redis_key = f"idemp:{str(user_id)}:{key}"

        # Cache in Redis
        payload = {"status_code": status_code, "body": response_body}
        await r.set(redis_key, json.dumps(payload), ex=IDEMPOTENCY_TTL_SECONDS)

        # Persist in DB
        if db:
            record = IdempotencyKey(
                key=key,
                user_id=user_id,
                request_hash=request_hash,
                response_code=status_code,
                response_body=response_body,
            )
            db.add(record)
            try:
                await db.commit()
            except Exception:
                await db.rollback()
