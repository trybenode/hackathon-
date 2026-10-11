"""Authenticate same-origin proxy IP forwarding; used by API middleware, never account sign-in."""
import hmac
import ipaddress
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.config import get_settings


class ProductionProxyMiddleware(BaseHTTPMiddleware):
    """Accept client IP only from our server proxy; protect session-backed mutations."""
    async def dispatch(self, request: Request, call_next):
        cfg = get_settings()
        key = request.headers.get('x-trust-proxy-key', '')
        address = request.headers.get('x-trust-client-ip', '')
        if cfg.internal_proxy_secret and hmac.compare_digest(key.encode(), cfg.internal_proxy_secret.encode()):
            try:
                ip = str(ipaddress.ip_address(address))
            except ValueError:
                ip = ''
            if ip:
                request.scope['client'] = (ip, 0)
        request.scope['headers'] = [(name, value) for name, value in request.scope['headers'] if name.lower() not in {b'x-trust-proxy-key', b'x-trust-client-ip'}]
        if cfg.environment != 'development' and request.method not in {'GET', 'HEAD', 'OPTIONS'} and (request.cookies.get('guarantor_session') or request.cookies.get('history_recipient')):
            if request.headers.get('origin') not in cfg.cors_origin_list:
                return JSONResponse({'detail': 'This request origin is not permitted.', 'code': 'ORIGIN_REJECTED'}, status_code=403, headers={'Cache-Control': 'no-store'})
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
