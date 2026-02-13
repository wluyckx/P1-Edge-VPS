"""
VPS configuration from environment variables using Pydantic BaseSettings.

All configuration values are loaded from environment variables at startup.
No hardcoded IPs, URLs, or credentials.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)

TODO:
- None
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """VPS application settings loaded from environment variables.

    Attributes:
        DATABASE_URL: PostgreSQL connection string (asyncpg).
        REDIS_URL: Redis connection string.
        DEVICE_TOKENS: Comma-separated token:device_id pairs for authentication.
        CACHE_TTL_S: Redis cache TTL in seconds.
    """

    DATABASE_URL: str
    REDIS_URL: str
    DEVICE_TOKENS: str
    CACHE_TTL_S: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    """Create and return a Settings instance.

    Returns:
        Settings: Validated configuration from environment variables.
    """
    return Settings()
