from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.request_metrics import request_metrics


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = int(response.status_code)
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            request_metrics.record(
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=elapsed_ms,
            )

