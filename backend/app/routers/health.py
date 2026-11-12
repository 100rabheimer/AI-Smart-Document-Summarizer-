from fastapi import APIRouter, status, Response
from app.core.config import get_settings
from app.core.database import check_db_health
from app.core.redis import check_redis_health
from app.schemas.health import HealthResponse, DependencyStatus

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and dependency check",
    description="Verifies operational status of the API, PostgreSQL database, and Redis cache."
)
async def health_check(response: Response):
    db_alive = await check_db_health()
    redis_alive = await check_redis_health()

    is_healthy = db_alive and redis_alive

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if is_healthy else "degraded",
        environment=settings.ENVIRONMENT,
        dependencies=DependencyStatus(
            database=db_alive,
            redis=redis_alive,
        )
    )
