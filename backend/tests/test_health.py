import pytest
from fastapi import Response
from unittest.mock import AsyncMock, patch

from app.main import root
from app.routers.health import health_check
from app.schemas.health import HealthResponse


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify that root endpoint returns application metadata."""
    res = await root()
    assert res["app"] == "DocMind"
    assert res["status"] == "online"


@pytest.mark.asyncio
async def test_health_endpoint_healthy():
    """Verify that /health reports 'ok' when all dependencies are healthy."""
    response = Response()
    with patch("app.routers.health.check_db_health", new_callable=AsyncMock) as mock_db, \
         patch("app.routers.health.check_redis_health", new_callable=AsyncMock) as mock_redis:
        mock_db.return_value = True
        mock_redis.return_value = True

        result: HealthResponse = await health_check(response=response)
        
        assert response.status_code == 200
        assert result.status == "ok"
        assert result.dependencies.database is True
        assert result.dependencies.redis is True


@pytest.mark.asyncio
async def test_health_endpoint_degraded():
    """Verify that /health sets status 503 and reports 'degraded' when a dependency is down."""
    response = Response()
    with patch("app.routers.health.check_db_health", new_callable=AsyncMock) as mock_db, \
         patch("app.routers.health.check_redis_health", new_callable=AsyncMock) as mock_redis:
        mock_db.return_value = False
        mock_redis.return_value = True

        result: HealthResponse = await health_check(response=response)
        
        assert response.status_code == 503
        assert result.status == "degraded"
        assert result.dependencies.database is False
        assert result.dependencies.redis is True
