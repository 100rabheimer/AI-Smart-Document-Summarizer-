import redis.asyncio as aioredis
from app.core.config import get_settings

settings = get_settings()

redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=20,
)

redis_client = aioredis.Redis(connection_pool=redis_pool)


async def get_redis() -> aioredis.Redis:
    """Dependency injection helper for FastAPI routes to access Redis."""
    return redis_client


async def check_redis_health() -> bool:
    """Verifies Redis connectivity via ping."""
    try:
        res = await redis_client.ping()
        return res is True
    except Exception:
        return False
