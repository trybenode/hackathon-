"""Purpose: Construct the FastAPI application and register middleware/routes.

Dependencies: FastAPI, CORS middleware, app.core.config, and health endpoints.
Used by: Uvicorn and ASGI test clients.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.guarantor import router as guarantor_router
from app.api.v1.endpoints.me import router as me_router
from app.api.v1.endpoints.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
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
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(guarantor_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(me_router, prefix=settings.api_v1_prefix)
