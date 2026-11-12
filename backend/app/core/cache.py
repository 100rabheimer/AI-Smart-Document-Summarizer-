import hashlib
import json
from typing import Optional, Any
from redis.asyncio import Redis

from app.core.redis import redis_client

DEFAULT_CACHE_TTL_SECONDS = 3600 * 24  # 24 hours


class CacheService:
    """
    Manages response caching using the O(1) Document-Version Invalidation Pattern.
    """

    @staticmethod
    def normalize_query(query: str) -> str:
        """Normalizes question string (lowercase, stripped whitespace)."""
        return " ".join(query.strip().lower().split())

    @classmethod
    def hash_query(cls, query: str) -> str:
        """Produces SHA-256 hash of normalized query."""
        normalized = cls.normalize_query(query)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    async def get_docs_version(user_id: str, client: Optional[Redis] = None) -> int:
        """
        Gets the current docs_version integer for a user.
        Defaults to 1 if not yet set in Redis.
        """
        r = client or redis_client
        key = f"docs_version:{user_id}"
        version = await r.get(key)
        if version is None:
            await r.set(key, 1)
            return 1
        return int(version)

    @staticmethod
    async def invalidate_user_docs_cache(user_id: str, client: Optional[Redis] = None) -> int:
        """
        O(1) Cache Invalidation:
        Atomically increments the user's docs_version counter.
        Instantly invalidates all prior cached queries without any KEYS scanning.
        """
        r = client or redis_client
        key = f"docs_version:{user_id}"
        return await r.incr(key)

    @classmethod
    async def get_cached_rag_response(
        cls,
        user_id: str,
        query: str,
        client: Optional[Redis] = None
    ) -> Optional[dict]:
        """
        Checks Redis for a previously cached answer for this specific query
        under the user's current document version.
        """
        r = client or redis_client
        version = await cls.get_docs_version(user_id=user_id, client=r)
        q_hash = cls.hash_query(query)
        cache_key = f"rag_cache:{user_id}:v{version}:{q_hash}"

        cached_data = await r.get(cache_key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except Exception:
                return None
        return None

    @classmethod
    async def set_cached_rag_response(
        cls,
        user_id: str,
        query: str,
        response_payload: dict,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        client: Optional[Redis] = None
    ) -> None:
        """
        Caches an answer tagged with the user's current docs_version.
        """
        r = client or redis_client
        version = await cls.get_docs_version(user_id=user_id, client=r)
        q_hash = cls.hash_query(query)
        cache_key = f"rag_cache:{user_id}:v{version}:{q_hash}"

        await r.set(
            name=cache_key,
            value=json.dumps(response_payload),
            ex=ttl_seconds
        )
