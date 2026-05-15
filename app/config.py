from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — SQLite dev default; swap DATABASE_URL in .env for Postgres
    database_url: str = "sqlite:///./crossconnect.db"

    # Session secret — override in production
    secret_key: str = "change-me-in-production"
    session_max_age: int = 86400  # 1 day in seconds

    # App metadata
    app_title: str = "CrossConnect"
    app_version: str = "0.1.0"


settings = Settings()
