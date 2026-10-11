"""Feature errors, secret-safe access logs and accurate OpenAPI security."""
import logging
import re
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.services.portability import FeatureError


class RedactVerificationToken(logging.Filter):
    """Redact public-link bearer paths in Uvicorn access logs."""
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            args = list(record.args)
            args[2] = re.sub(r"((?:/[^? /]+)*/(?:verification|history-confirmations|verify|confirm-work)/)[^? /]+", r"\1[redacted]", str(args[2]))
            record.args = tuple(args)
        return True


class PrivateResponses(BaseHTTPMiddleware):
    """Never cache mutable consent/records and do not send bearer URLs as referrers."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if any(segment in request.url.path for segment in ("/me/", "/verification/", "/history-confirmations/", "/platform/", "/credentials/", "/review")):
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response


def install_feature_http(app) -> None:
    """Register feature errors and OpenAPI schemes without altering sign-in."""
    logging.getLogger("uvicorn.access").addFilter(RedactVerificationToken())
    app.add_middleware(PrivateResponses)

    @app.exception_handler(FeatureError)
    async def feature_error(request: Request, error: FeatureError):
        headers = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
        if error.retry_after is not None:
            headers["Retry-After"] = str(error.retry_after)
        return JSONResponse(status_code=error.status, content={"detail": error.detail, "code": error.code}, headers=headers)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException):
        codes = {401: "AUTH_REQUIRED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 429: "RATE_LIMITED", 503: "SERVICE_UNAVAILABLE"}
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail, "code": codes.get(error.status_code, "REQUEST_FAILED")}, headers={"Cache-Control": "no-store", **(error.headers or {})})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        # Validation messages only: never echo input values, tokens or documents.
        return JSONResponse(status_code=422, content={"detail": "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()), "code": "INVALID_INPUT"}, headers={"Cache-Control": "no-store"})

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        schema.setdefault("components", {}).setdefault("securitySchemes", {}).update({
            "UserSession": {"type": "apiKey", "in": "cookie", "name": "guarantor_session", "description": "Existing signed-in session. These features do not create accounts or change sign-in."},
            "HistoryRecipient": {"type": "apiKey", "in": "cookie", "name": "history_recipient", "description": "Short-lived access limited to one contact-verified history request. This is not an account session. Native jobs require the existing hiring-customer UserSession instead."},
            "PlatformKey": {"type": "apiKey", "in": "header", "name": "X-API-Key", "description": "Dedicated platform key with live worker consent; legacy shared keys are limited to development trust queries."}})
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                if not isinstance(operation, dict) or method not in ("get", "post", "delete", "patch", "put"):
                    continue
                # Python 3.12 and 3.14 use different phrases for HTTP 422.
                # Keep the published contract stable without overriding custom
                # descriptions or FastAPI's "Validation Error" response.
                invalid_input = operation.get("responses", {}).get("422", {})
                if invalid_input.get("description") in {"Unprocessable Entity", "Unprocessable Content"}:
                    invalid_input["description"] = "Unprocessable Content"
                if "/history-confirmations/" in path:
                    if path.endswith(("/challenge", "/challenge/check")):
                        operation["security"] = []
                    elif method == "get" and path.endswith("/{token}"):
                        operation["security"] = [{}, {"HistoryRecipient": []}, {"UserSession": []}]
                    else:
                        operation["security"] = [{"HistoryRecipient": []}, {"UserSession": []}]
                    operation["description"] = operation.get("description", "") + "\nThe link alone never authorizes private details, messages or decisions. Contact control establishes no historical hiring relationship; native jobs match the live hiring account. No history operation changes protected-review eligibility or trust scoring."
                elif "/platform/" in path or path.endswith("/trust/query"):
                    operation["security"] = [{"PlatformKey": []}]
                elif "/me/" in path or "/review" in path or "/credentials/" in path:
                    operation["security"] = [{"UserSession": []}]
        app.openapi_schema = schema
        return schema
    app.openapi = openapi
