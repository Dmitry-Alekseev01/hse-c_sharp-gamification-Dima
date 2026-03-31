import asyncio
import json
import logging
from typing import Optional

from app.cache.redis_cache import delete_pattern, get_redis_client
from app.db.session import AsyncSessionLocal
from app.models.answer import Answer
from app.repositories import analytics_repo, test_attempt_repo

logger = logging.getLogger("worker")


async def process_job(job_payload: str) -> None:
    try:
        data = json.loads(job_payload)
    except Exception:
        logger.exception("Invalid job payload (not json): %s", job_payload)
        return

    answer_id = data.get("answer_id")
    user_id = data.get("user_id")
    logger.info("Open answer queued for manual grading: answer_id=%s user_id=%s", answer_id, user_id)

    if answer_id is None:
        logger.warning("Job missing answer_id: %s", data)
        return

    # ensure record exists (do not modify schema here)
    async with AsyncSessionLocal() as session:
        ans: Optional[Answer] = await session.get(Answer, answer_id)
        if ans:
            logger.info("Found answer %s for manual grading (user_id=%s)", answer_id, ans.user_id)
        else:
            logger.warning("Answer %s not found in DB", answer_id)


async def process_answer_postprocess(job_payload: str) -> None:
    try:
        data = json.loads(job_payload)
    except Exception:
        logger.exception("Invalid analytics job payload: %s", job_payload)
        return

    user_id = data.get("user_id")
    test_id = data.get("test_id")
    attempt_id = data.get("attempt_id")
    points_delta = float(data.get("points_delta") or 0.0)
    mark_active = bool(data.get("mark_active"))

    if user_id is None or test_id is None:
        logger.warning("Analytics job missing identifiers: %s", data)
        return

    async with AsyncSessionLocal() as session:
        try:
            if points_delta != 0 or mark_active:
                await analytics_repo.create_or_update_analytics(
                    session,
                    user_id=user_id,
                    points_delta=points_delta,
                    mark_active=mark_active,
                )
            if attempt_id is not None:
                attempt = await test_attempt_repo.get_attempt(session, int(attempt_id))
                if attempt is not None:
                    await test_attempt_repo.refresh_attempt_scores(session, attempt)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to process answer postprocess job: %s", data)
            return

    try:
        await delete_pattern("leaderboard:top:*")
        await delete_pattern(f"test:{test_id}:summary*")
        await delete_pattern(f"user:{user_id}:analytics*")
    except Exception:
        logger.exception("Failed to invalidate caches after answer postprocess for test=%s user=%s", test_id, user_id)


async def run_worker() -> None:
    r = get_redis_client()
    logger.info("Worker started: polling grading:open and answers:postprocess")
    while True:
        try:
            # BLPOP returns tuple (key, value) or None
            item = await r.blpop(["grading:open", "answers:postprocess"], timeout=5)
            if not item:
                # timeout - loop again (allows graceful shutdown)
                await asyncio.sleep(0.1)
                continue
            queue_name, payload = item
            if queue_name == "grading:open":
                await process_job(payload)
            elif queue_name == "answers:postprocess":
                await process_answer_postprocess(payload)
        except asyncio.CancelledError:
            logger.info("Worker cancelled, exiting")
            break
        except Exception:
            logger.exception("Worker loop error, sleeping briefly")
            await asyncio.sleep(1)


if __name__ == "__main__":
    import sys
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by KeyboardInterrupt")
