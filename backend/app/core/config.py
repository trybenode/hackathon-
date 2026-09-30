"""Purpose: Load and normalize application configuration, including Neon URLs.

Dependencies: pydantic-settings, pathlib, urllib.parse.
Used by: app.db.session, app.main, and Alembic.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    #: `.env` holds the shared settings; `.env.local` overrides them per
    #: machine, which is how local development points at a local Postgres
    #: instead of Neon. Later files win.
    _REPO_ROOT = Path(__file__).resolve().parents[3]
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _REPO_ROOT / ".env.local"),
        extra="ignore",
    )

    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(
        "postgresql+asyncpg://placeholder:placeholder@localhost:5432/placeholder",
        alias="DATABASE_URL",
    )
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"

    #: Transactional email. Without a key, login codes are logged instead.
    resend_api_key: str = Field("", alias="RESEND_API_KEY")
    #: Resend only accepts a verified domain, or its shared onboarding sender.
    resend_from: str = Field("Trust Infrastructure <onboarding@resend.dev>", alias="RESEND_FROM")

    @property
    def email_enabled(self) -> bool:
        return bool(self.resend_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def async_database_url(self) -> str:
        """Convert Neon CLI connection strings to SQLAlchemy asyncpg URLs."""

        url = self.database_url
        parts = urlsplit(url)
        scheme = parts.scheme
        if scheme == "postgresql":
            scheme = "postgresql+asyncpg"

        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if "sslmode" in query:
            query["ssl"] = query.pop("sslmode")
        query.pop("channel_binding", None)

        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@lru_cache
def get_settings() -> Settings:
    return Settings()
