from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.points_ledger import PointsLedger
from app.repositories import analytics_repo, challenge_repo
from app.services import reward_service


class ChallengePeriodType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class ChallengeEventType(str, Enum):
    ANSWER_SUBMITTED = "answer_submitted"
    ATTEMPT_COMPLETED = "attempt_completed"
    STREAK_DAY = "streak_day"


class ChallengeClaimError(Exception):
    pass


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def resolve_period_key(period_type: str, moment: datetime) -> str:
    if period_type == ChallengePeriodType.DAILY.value:
        return moment.date().isoformat()
    if period_type == ChallengePeriodType.WEEKLY.value:
        iso_year, iso_week, _ = moment.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    raise ValueError(f"Unsupported challenge period_type: {period_type}")


def _challenge_is_active_now(challenge, moment: datetime) -> bool:
    if not challenge.is_active:
        return False
    if challenge.starts_at is not None and challenge.starts_at > moment:
        return False
    if challenge.ends_at is not None and challenge.ends_at < moment:
        return False
    return True


async def create_challenge(
    session: AsyncSession,
    *,
    code: str,
    title: str,
    description: str | None,
    period_type: ChallengePeriodType,
    event_type: ChallengeEventType,
    target_value: int,
    reward_points: float,
    is_active: bool,
    starts_at: datetime | None,
    ends_at: datetime | None,
    created_by: int | None,
):
    if target_value < 1:
        raise ValueError("target_value must be >= 1")
    if reward_points < 0:
        raise ValueError("reward_points must be >= 0")
    if starts_at is not None and ends_at is not None and ends_at < starts_at:
        raise ValueError("ends_at must be greater than or equal to starts_at")
    existing = await challenge_repo.get_challenge_by_code(session, code)
    if existing is not None:
        raise ValueError("Challenge code already exists")

    challenge = await challenge_repo.create_challenge(
        session,
        code=code,
        title=title,
        description=description,
        period_type=period_type.value,
        event_type=event_type.value,
        target_value=target_value,
        reward_points=reward_points,
        is_active=is_active,
        starts_at=starts_at,
        ends_at=ends_at,
        created_by=created_by,
    )
    await session.refresh(challenge)
    return challenge


async def record_event(
    session: AsyncSession,
    *,
    user_id: int,
    event_type: ChallengeEventType,
    increment: int = 1,
    occurred_at: datetime | None = None,
) -> list[dict[str, Any]]:
    moment = occurred_at or utcnow_naive()
    increment_value = max(int(increment), 0)
    active_challenges = await challenge_repo.list_active_challenges(
        session,
        moment=moment,
        event_type=event_type.value,
    )
    updated: list[dict[str, Any]] = []

    for challenge in active_challenges:
        period_key = resolve_period_key(challenge.period_type, moment)
        progress = await challenge_repo.get_user_challenge_progress(
            session,
            user_id=user_id,
            challenge_id=challenge.id,
            period_key=period_key,
        )
        if progress is None:
            progress = await challenge_repo.create_user_challenge_progress(
                session,
                user_id=user_id,
                challenge_id=challenge.id,
                period_key=period_key,
                progress_value=0,
            )

        before = int(progress.progress_value or 0)
        if event_type == ChallengeEventType.STREAK_DAY and challenge.period_type == ChallengePeriodType.DAILY.value:
            after = max(before, 1)
        else:
            after = before + increment_value

        progress.progress_value = after
        if progress.completed_at is None and after >= int(challenge.target_value or 0):
            progress.completed_at = moment

        updated.append(
            {
                "challenge_id": challenge.id,
                "period_key": period_key,
                "progress_value": int(progress.progress_value or 0),
                "completed_at": progress.completed_at,
            }
        )

    await session.flush()
    return updated


async def list_active_challenges_with_progress(
    session: AsyncSession,
    *,
    user_id: int,
    moment: datetime | None = None,
) -> list[dict[str, Any]]:
    now = moment or utcnow_naive()
    challenges = await challenge_repo.list_active_challenges(session, moment=now)
    if not challenges:
        return []

    period_key_by_id: dict[int, str] = {
        challenge.id: resolve_period_key(challenge.period_type, now) for challenge in challenges
    }
    challenge_ids = [challenge.id for challenge in challenges]
    period_keys = list(period_key_by_id.values())
    progress_rows = await challenge_repo.list_user_progress_for_challenges(
        session,
        user_id=user_id,
        challenge_ids=challenge_ids,
        period_keys=period_keys,
    )
    claim_rows = await challenge_repo.list_user_claims_for_challenges(
        session,
        user_id=user_id,
        challenge_ids=challenge_ids,
        period_keys=period_keys,
    )

    progress_map = {(row.challenge_id, row.period_key): row for row in progress_rows}
    claim_map = {(row.challenge_id, row.period_key): row for row in claim_rows}
    items: list[dict[str, Any]] = []
    for challenge in challenges:
        period_key = period_key_by_id[challenge.id]
        progress = progress_map.get((challenge.id, period_key))
        claim = claim_map.get((challenge.id, period_key))
        progress_value = int(progress.progress_value) if progress is not None and progress.progress_value is not None else 0
        is_completed = progress is not None and progress.completed_at is not None
        if not is_completed:
            is_completed = progress_value >= int(challenge.target_value or 0)
        items.append(
            {
                "challenge_id": challenge.id,
                "code": challenge.code,
                "title": challenge.title,
                "description": challenge.description,
                "period_type": challenge.period_type,
                "event_type": challenge.event_type,
                "target_value": int(challenge.target_value),
                "reward_points": float(challenge.reward_points or 0.0),
                "period_key": period_key,
                "progress_value": progress_value,
                "is_completed": bool(is_completed),
                "is_claimed": claim is not None,
                "completed_at": progress.completed_at if progress is not None else None,
                "claimed_at": claim.claimed_at if claim is not None else None,
            }
        )
    return items


async def claim_challenge(
    session: AsyncSession,
    *,
    user_id: int,
    challenge_id: int,
    moment: datetime | None = None,
) -> dict[str, Any]:
    now = moment or utcnow_naive()
    challenge = await challenge_repo.get_challenge(session, challenge_id)
    if challenge is None:
        raise ChallengeClaimError("Challenge not found")
    if not _challenge_is_active_now(challenge, now):
        raise ChallengeClaimError("Challenge is not active")

    period_key = resolve_period_key(challenge.period_type, now)
    progress = await challenge_repo.get_user_challenge_progress(
        session,
        user_id=user_id,
        challenge_id=challenge_id,
        period_key=period_key,
    )
    if progress is None or int(progress.progress_value or 0) < int(challenge.target_value or 0):
        raise ChallengeClaimError("Challenge is not completed for current period")

    existing_claim = await challenge_repo.get_user_challenge_claim(
        session,
        user_id=user_id,
        challenge_id=challenge_id,
        period_key=period_key,
    )
    if existing_claim is not None:
        raise ChallengeClaimError("Challenge reward already claimed for current period")

    idempotency_key = f"challenge_claim:{user_id}:{challenge_id}:{period_key}"
    await analytics_repo.apply_points_delta(
        session,
        user_id=user_id,
        points_delta=float(challenge.reward_points or 0.0),
        reason_code="challenge_claim",
        source_type="challenge",
        source_id=challenge_id,
        idempotency_key=idempotency_key,
        metadata={
            "challenge_id": challenge_id,
            "challenge_code": challenge.code,
            "period_key": period_key,
        },
    )
    ledger_entry_id = await session.scalar(
        select(PointsLedger.id).where(PointsLedger.idempotency_key == idempotency_key).limit(1)
    )
    claim = await challenge_repo.create_user_challenge_claim(
        session,
        user_id=user_id,
        challenge_id=challenge_id,
        period_key=period_key,
        reward_points=float(challenge.reward_points or 0.0),
        ledger_entry_id=int(ledger_entry_id) if ledger_entry_id is not None else None,
    )
    await reward_service.sync_user_rewards(session, user_id)
    await session.flush()
    return {
        "challenge_id": challenge_id,
        "period_key": period_key,
        "reward_points": float(claim.reward_points or 0.0),
        "claimed_at": claim.claimed_at,
    }
