"""Purpose: Construct the FastAPI application and register middleware/routes.

Dependencies: FastAPI, CORS middleware, app.core.config, and health endpoints.
Used by: Uvicorn and ASGI test clients.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.developers import router as developers_router
from app.api.v1.endpoints.scoring import router as scoring_router
from app.core.api_usage import ApiUsageMiddleware
from app.api.v1.endpoints.guarantor import router as guarantor_router
from app.api.v1.endpoints.me import router as me_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.trust import router as trust_router
from app.api.v1.endpoints.credentials import router as credentials_router
from app.api.v1.endpoints.portability import router as portability_router, platform_router
from app.core.feature_http import install_feature_http
from app.api.v1.endpoints.worker_record import router as worker_record_router
from app.api.v1.endpoints.onboarding import router as onboarding_router
from app.api.v1.endpoints.jobs import (
    payscrow_webhook,
    public_router as public_jobs_router,
    webhook_router,
    worker_feed_router,
    worker_router as my_jobs_router,
)
from app.api.v1.endpoints.history import router as history_router
from app.core.production_http import ProductionProxyMiddleware
from app.core.production import validate_production_settings
from app.core.config import get_settings
from app.db.session import async_session_factory
from app.services.expiry import sweep_forever

settings = get_settings()
if settings.deployment_mode == "serverless":
    validate_production_settings(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run the expiry sweep alongside the app.

    Expiry is time-based, so without this an instrument stays Active past its
    validity date. Tests drive the app through ASGITransport, which does not
    run lifespan, so the loop never starts there.
    """

    validate_production_settings(settings)
    task: asyncio.Task | None = None
    if settings.deployment_mode != "serverless" and settings.expiry_sweep_seconds > 0:
        task = asyncio.create_task(
            sweep_forever(async_session_factory, settings.expiry_sweep_seconds)
        )
        logger.info("Expiry sweep running every %ds", settings.expiry_sweep_seconds)

    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    lifespan=lifespan,
    title="Dynamic Trust Infrastructure API",
    version="0.1.0",
    description="Trust scoring and portable work verification infrastructure.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(ApiUsageMiddleware)
install_feature_http(app)
app.add_middleware(ProductionProxyMiddleware)

app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(guarantor_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(developers_router, prefix=settings.api_v1_prefix)
app.include_router(scoring_router, prefix=settings.api_v1_prefix)
app.include_router(me_router, prefix=settings.api_v1_prefix)
app.include_router(trust_router, prefix=settings.api_v1_prefix)
app.include_router(credentials_router, prefix=settings.api_v1_prefix)
app.include_router(portability_router, prefix=settings.api_v1_prefix)
app.include_router(platform_router, prefix=settings.api_v1_prefix)
app.include_router(worker_record_router, prefix=settings.api_v1_prefix)
app.include_router(onboarding_router, prefix=settings.api_v1_prefix)
app.include_router(public_jobs_router, prefix=settings.api_v1_prefix)
app.include_router(my_jobs_router, prefix=settings.api_v1_prefix)
app.include_router(worker_feed_router, prefix=settings.api_v1_prefix)
app.include_router(webhook_router, prefix=settings.api_v1_prefix)
# Payscrow retries a webhook at the address the transaction was opened with.
# Transactions opened while PAYSCROW_WEBHOOK_URL was a bare host point at "/",
# so the same signed handler answers there too.
app.add_api_route("/", payscrow_webhook, methods=["POST"], include_in_schema=False)
app.include_router(history_router, prefix=settings.api_v1_prefix)
