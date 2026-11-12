from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "DocMind"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = True
    APP_SECRET_KEY: str = "dev-secret-key-change-in-production-min-32-bytes"

    # Database Settings
    POSTGRES_USER: str = "docmind"
    POSTGRES_PASSWORD: str = "docmind_secret"
    POSTGRES_DB: str = "docmind_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://docmind:docmind_secret@localhost:5432/docmind_db"

    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"

    # Google OAuth 2.0 Settings
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/callback/google"

    # Frontend Settings
    FRONTEND_URL: str = "http://localhost:5173"

    # AI & Embedding Settings
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "models/text-embedding-004"
    EMBEDDING_DIMENSION: int = 768
    CHAT_MODEL: str = "gemini-1.5-flash"

    # Local Storage Settings
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_DIR: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 10

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings singleton so the .env file is read once
    and reused across the application lifecycle.
    """
    return Settings()
