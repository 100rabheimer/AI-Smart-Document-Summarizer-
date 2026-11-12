import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request, HTTPException, status

from app.core.cache import CacheService
from app.core.rate_limiter import RateLimiter
from app.core.idempotency import IdempotencyService


def test_query_normalization_and_hash():
    """Verify that case and whitespace differences map to the identical cache hash."""
    q1 = "   What IS the Document Summary?  "
    q2 = "what is the document summary?"
    q3 = "what   is the   document    summary? "

    h1 = CacheService.hash_query(q1)
    h2 = CacheService.hash_query(q2)
    h3 = CacheService.hash_query(q3)

    assert h1 == h2 == h3
    assert len(h1) == 64


@pytest.mark.asyncio
async def test_docs_version_cache_invalidation():
    """
    Verify the O(1) version invalidation:
    Incrementing docs_version renders all prior query caches naturally unreachable.
    """
    mock_redis = AsyncMock()
    user_id = "user-123"
    query = "What is the refund policy?"

    # Step 1: Version is 1
    mock_redis.get.side_effect = [
        "1",  # get_docs_version in get_cached_rag_response
        '{"answer": "Old answer", "citations": []}',  # get cache_key v1
    ]

    cached = await CacheService.get_cached_rag_response(user_id=user_id, query=query, client=mock_redis)
    assert cached is not None
    assert cached["answer"] == "Old answer"

    # Step 2: Document uploaded or deleted -> bump version
    mock_redis.incr.return_value = 2
    new_version = await CacheService.invalidate_user_docs_cache(user_id=user_id, client=mock_redis)
    assert new_version == 2

    # Step 3: Subsequent query now checks v2 (cache miss)
    mock_redis.get.side_effect = [
        "2",   # get_docs_version in get_cached_rag_response
        None,  # cache_key v2 does not exist yet
    ]

    cached_after_bump = await CacheService.get_cached_rag_response(user_id=user_id, query=query, client=mock_redis)
    assert cached_after_bump is None


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter_allowed():
    """Verify that requests within limit pass through successfully."""
    mock_redis = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_pipeline.__aexit__ = AsyncMock(return_value=None)
    # pipeline returns [zremrangebyscore_count, zcard_count=3, zadd_result, expire_result]
    mock_pipeline.execute = AsyncMock(return_value=[0, 3, 1, True])
    # pipeline() is a sync call returning the async context manager
    mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

    limiter = RateLimiter(max_requests=10, window_seconds=60, redis=mock_redis)
    mock_request = Request({"type": "http", "headers": [], "path": "/api/v1/conversations/1/messages"})

    allowed = await limiter(request=mock_request)
    assert allowed is True


@pytest.mark.asyncio
async def test_sliding_window_rate_limiter_exceeded():
    """Verify that exceeding limit raises HTTP 429 with Retry-After header."""
    mock_redis = AsyncMock()
    mock_pipeline = MagicMock()
    mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_pipeline.__aexit__ = AsyncMock(return_value=None)
    # pipeline returns count = 10 (which equals or exceeds max_requests=10)
    mock_pipeline.execute = AsyncMock(return_value=[0, 10, 1, True])
    # pipeline() is a sync call returning the async context manager
    mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

    limiter = RateLimiter(max_requests=10, window_seconds=60, redis=mock_redis)
    mock_request = Request({"type": "http", "headers": [], "path": "/api/v1/conversations/1/messages"})

    with pytest.raises(HTTPException) as exc_info:
        await limiter(request=mock_request)

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in exc_info.value.headers
    assert exc_info.value.headers["Retry-After"] == "60"


@pytest.mark.asyncio
async def test_idempotency_service_cache_and_retrieve():
    """Verify storing and replaying responses using idempotency keys."""
    mock_redis = AsyncMock()
    user_id = uuid.uuid4()
    idemp_key = "idemp-client-uuid-999"

    # 1. Record response
    await IdempotencyService.record_response(
        user_id=user_id,
        key=idemp_key,
        request_hash="sha256-hash-of-file-bytes",
        status_code=201,
        response_body={"document_id": "doc-uuid-1", "status": "uploaded"},
        db=None,
        client=mock_redis,
    )
    mock_redis.set.assert_called_once()

    # 2. Replay lookup (Cache Hit)
    mock_redis.get.return_value = '{"status_code": 201, "body": {"document_id": "doc-uuid-1", "status": "uploaded"}}'

    cached = await IdempotencyService.get_cached_response(
        user_id=user_id,
        key=idemp_key,
        db=None,
        client=mock_redis,
    )
    assert cached is not None
    status_code, body = cached
    assert status_code == 201
    assert body["document_id"] == "doc-uuid-1"
