"""Configuration management using Pydantic settings."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Database
    DATABASE_PATH: str = "/app/data/triage.db"

    # Feed fetching
    FEED_REFRESH_MINUTES: int = 15
    MAX_ITEMS_PER_FEED: int = 50
    FEED_PARALLEL_WORKERS: int = 5
    FEED_TIMEOUT_SECONDS: int = 30

    # Webhook
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_TIMEOUT_SECONDS: int = 10
    WEBHOOK_RETRY_COUNT: int = 3

    # Digest
    DIGEST_OUTPUT_PATH: str = "/app/digests"
    DIGEST_GENERATION_TIME: str = "09:00"  # HH:MM format
    TIMEZONE: str = "Pacific/Auckland"

    # Web interface
    PORT: int = 8083
    HOST: str = "0.0.0.0"

    # Authentication
    AUTH_TOKEN: Optional[str] = None
    USER_IDENTIFIER: str = "apth"

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
