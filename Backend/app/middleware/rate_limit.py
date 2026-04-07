import time

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
        if request.method == "OPTIONS" or not path.startswith("/api/"):
            return await call_next(request)

        identifier = self._get_identifier(request)
        scope, limit = self._get_scope_and_limit(path)
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
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    @staticmethod
    def _get_scope_and_limit(path: str) -> tuple[str, int]:
        if path.startswith("/api/v1/auth/"):
            return "auth", settings.rate_limit_auth
        if path.startswith("/api/v1/answers/"):
            return "answers", settings.rate_limit_answers
        if path.startswith("/api/v1/analytics/"):
            return "analytics", settings.rate_limit_analytics
        return "default", settings.rate_limit_default
