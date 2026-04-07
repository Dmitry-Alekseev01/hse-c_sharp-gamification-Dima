"""Health endpoints used by liveness/readiness probes."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from app.db.session import engine
from app.cache.redis_cache import get_redis_client

router = APIRouter()

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
