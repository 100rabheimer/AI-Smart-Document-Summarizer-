from pydantic import BaseModel


class DependencyStatus(BaseModel):
    database: bool
    redis: bool


class HealthResponse(BaseModel):
    status: str
    environment: str
    dependencies: DependencyStatus
