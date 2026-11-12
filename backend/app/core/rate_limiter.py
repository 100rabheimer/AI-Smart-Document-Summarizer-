import time
from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from redis.asyncio import Redis

from app.core.redis import redis_client


class RateLimiter:
    """
    Sliding-window rate limiter powered by Redis Sorted Sets (ZSET).
    Enforces continuous time-window limits without boundary bursting.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        key_prefix: str = "rate_limit",
        redis: Optional[Redis] = None,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self.redis = redis

    async def __call__(
        self,
        request: Request,
    ) -> bool:
        r = self.redis or redis_client

        # Identify client: Prefer authenticated user_id, fallback to client IP
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            client_id = f"user:{str(user.id)}"
        else:
            client_ip = request.client.host if request.client else "unknown_ip"
            client_id = f"ip:{client_ip}"

        redis_key = f"{self.key_prefix}:{client_id}:{request.url.path}"
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - (self.window_seconds * 1000)

        # Execute sliding window pipeline in Redis
        async with r.pipeline(transaction=True) as pipe:
            # 1. Purge events older than current sliding window
            pipe.zremrangebyscore(redis_key, 0, window_start_ms)
            # 2. Count requests inside the active window
            pipe.zcard(redis_key)
            # 3. Add current timestamp
            pipe.zadd(redis_key, {str(now_ms): now_ms})
            # 4. Set expiry to auto-cleanup inactive keys
            pipe.expire(redis_key, self.window_seconds + 5)
            
            results = await pipe.execute()

        current_count = results[1]

        if current_count >= self.max_requests:
            # Remove the request that just exceeded the limit
            await r.zrem(redis_key, str(now_ms))
            
            retry_after = self.window_seconds
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Allowed: {self.max_requests} requests per {self.window_seconds}s.",
                headers={"Retry-After": str(retry_after)},
            )

        return True


# Preconfigured rate limiter dependencies
# 1. Strict limit for expensive LLM Chat: 20 queries per minute
chat_rate_limiter = RateLimiter(max_requests=20, window_seconds=60, key_prefix="rl_chat")

# 2. Upload limit: 10 document uploads per minute
upload_rate_limiter = RateLimiter(max_requests=10, window_seconds=60, key_prefix="rl_upload")

# 3. General API limit: 120 requests per minute
general_rate_limiter = RateLimiter(max_requests=120, window_seconds=60, key_prefix="rl_general")
