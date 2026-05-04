"""Health endpoints used by liveness/readiness probes."""
from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import text

from app.cache.redis_cache import get_redis_client
from app.core.config import settings
from app.db.session import engine
from app.observability.request_metrics import request_metrics

router = APIRouter()


def _ensure_metrics_access(x_metrics_token: str | None) -> None:
    expected_token = settings.get_monitoring_metrics_token()
    if not expected_token:
        return
    if x_metrics_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Metrics access denied",
        )

@router.get("/live")
async def liveness():
    return {"status": "ok"}

@router.get("/ready")
async def readiness():
    # basic checks: DB connect and redis ping
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        r = get_redis_client()
        await r.ping()
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not ready", "reason": str(e)},
        )


@router.get("/metrics")
async def metrics(x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token")):
    _ensure_metrics_access(x_metrics_token)
    return request_metrics.snapshot()
