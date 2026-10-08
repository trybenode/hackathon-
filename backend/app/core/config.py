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

    #: How often the background sweep expires overdue instruments. Set to 0
    #: to disable it, e.g. when a scheduler calls the endpoint instead.
    expiry_sweep_seconds: int = Field(900, alias="EXPIRY_SWEEP_SECONDS")

    #: S3-compatible object storage for KYC documents. Without a bucket the
    #: document is validated and dropped.
    s3_bucket: str = Field("", alias="S3_BUCKET")
    aws_endpoint_url_s3: str = Field("", alias="AWS_ENDPOINT_URL_S3")
    aws_region: str = Field("", alias="AWS_REGION")
    #: boto3 reads the process environment, which does not see .env, so the
    #: credentials are passed to the client explicitly.
    aws_access_key_id: str = Field("", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field("", alias="AWS_SECRET_ACCESS_KEY")

    #: Transactional email. Without a key, login codes are logged instead.
    resend_api_key: str = Field("", alias="RESEND_API_KEY")
    #: Resend only accepts a verified domain, or its shared onboarding sender.
    resend_from: str = Field("Trust Infrastructure <onboarding@resend.dev>", alias="RESEND_FROM")
    credential_signing_secret: str = Field("", alias="CREDENTIAL_SIGNING_SECRET")
    platform_api_key: str = Field("", alias="PLATFORM_API_KEY")
    #: Payscrow escrow. Without a key, a local stand-in holds the money.
    payscrow_api_key: str = Field("", alias="PAYSCROW_API_KEY")
    #: The sandbox lives on .dev; production is https://api.payscrow.net.
    payscrow_base_url: str = Field("https://api.payscrow.dev", alias="PAYSCROW_BASE_URL")
    #: Verifies that webhooks really came from Payscrow.
    payscrow_webhook_secret: str = Field("", alias="PAYSCROW_WEBHOOK_SECRET")
    #: Public HTTPS address Payscrow posts to, e.g. a tunnel to this API.
    payscrow_webhook_url: str = Field("", alias="PAYSCROW_WEBHOOK_URL")
    #: Share of Payscrow's charge the worker bears, 0 to 100. 0: the client pays it.
    payscrow_merchant_charge_percentage: float = Field(0, alias="PAYSCROW_MERCHANT_CHARGE_PERCENTAGE")
    #: Hours a client has to confirm a completed job before funds release anyway.
    escrow_auto_release_hours: int = Field(72, alias="ESCROW_AUTO_RELEASE_HOURS")

    @property
    def escrow_enabled(self) -> bool:
        return bool(self.payscrow_api_key.strip())

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
