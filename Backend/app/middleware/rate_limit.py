import time
from ipaddress import ip_address

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.cache.redis_cache import get_redis_client
from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        admin_base = settings.admin_base_url.rstrip("/") or "/admin"
        is_admin_path = path == admin_base or path.startswith(f"{admin_base}/")
        if request.method == "OPTIONS" or (not path.startswith("/api/") and not is_admin_path):
            return await call_next(request)

        identifier = self._get_identifier(request)
        if is_admin_path and not self._is_admin_ip_allowed(identifier):
            return JSONResponse(status_code=403, content={"detail": "Admin access denied from this IP"})

        scope, limit = self._get_scope_and_limit(path, request.method)
        window = settings.rate_limit_window_seconds
        bucket = int(time.time() // window)
        key = f"rate:{scope}:{identifier}:{bucket}"

        client = get_redis_client()
        current = await client.incr(key)
        if current == 1:
            await client.expire(key, window + 1)

        remaining = max(limit - current, 0)
        reset_seconds = max(window - (int(time.time()) % window), 1)

        if current > limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)
        return response

    @staticmethod
    def _get_identifier(request: Request) -> str:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            parts = [part.strip() for part in forwarded_for.split(",") if part.strip()]
            if parts:
                # Use the last hop in XFF chain; it is less spoofable when request
                # passes through trusted reverse proxy appending client addresses.
                return parts[-1]

        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    @staticmethod
    def _normalize_identifier_ip(identifier: str) -> str:
        value = (identifier or "").strip()
        if not value:
            return value

        if value.startswith("[") and "]" in value:
            value = value[1 : value.index("]")]

        if value.count(":") == 1 and "." in value:
            host_part, port_part = value.rsplit(":", 1)
            if port_part.isdigit():
                value = host_part
        return value

    @staticmethod
    def _is_admin_ip_allowed(identifier: str) -> bool:
        try:
            networks = settings.get_admin_allowed_networks()
        except ValueError:
            return False
        if not networks:
            return True

        candidate = RateLimitMiddleware._normalize_identifier_ip(identifier)
        try:
            client_ip = ip_address(candidate)
        except ValueError:
            return False

        return any(client_ip in network for network in networks)

    @staticmethod
    def _get_scope_and_limit(path: str, method: str) -> tuple[str, int]:
        admin_base = settings.admin_base_url.rstrip("/") or "/admin"
        if path == f"{admin_base}/login" and method.upper() == "POST":
            return "admin_login", settings.rate_limit_admin_login
        if path == admin_base or path.startswith(f"{admin_base}/"):
            return "admin", settings.rate_limit_admin
        if path.startswith("/api/v1/auth/"):
            return "auth", settings.rate_limit_auth
        if path.startswith("/api/v1/answers/"):
            return "answers", settings.rate_limit_answers
        if path.startswith("/api/v1/analytics/"):
            return "analytics", settings.rate_limit_analytics
        if path.startswith("/api/v1/ai/"):
            return "ai", settings.rate_limit_ai
        return "default", settings.rate_limit_default
