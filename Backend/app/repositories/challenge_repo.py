from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge, UserChallengeClaim, UserChallengeProgress


def now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def create_challenge(
    session: AsyncSession,
    *,
    code: str,
    title: str,
    description: str | None,
    period_type: str,
    event_type: str,
    target_value: int,
    reward_points: float,
    is_active: bool,
    starts_at: datetime | None,
    ends_at: datetime | None,
    created_by: int | None,
) -> Challenge:
    now = now_utc_naive()
    challenge = Challenge(
        code=code,
        title=title,
        description=description,
        period_type=period_type,
        event_type=event_type,
        target_value=target_value,
        reward_points=reward_points,
        is_active=is_active,
        starts_at=starts_at,
        ends_at=ends_at,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    session.add(challenge)
    await session.flush()
    return challenge


async def list_challenges(
    session: AsyncSession,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[Challenge]:
    stmt = select(Challenge).order_by(Challenge.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_challenge(session: AsyncSession, challenge_id: int) -> Challenge | None:
    return await session.get(Challenge, challenge_id)


async def get_challenge_by_code(session: AsyncSession, code: str) -> Challenge | None:
    stmt = select(Challenge).where(Challenge.code == code).limit(1)
    return (await session.execute(stmt)).scalars().first()


async def update_challenge(
    session: AsyncSession,
    challenge_id: int,
    **changes,
) -> Challenge | None:
    challenge = await get_challenge(session, challenge_id)
    if challenge is None:
        return None

    if "code" in changes:
        challenge.code = changes["code"]
    if "title" in changes:
        challenge.title = changes["title"]
    if "description" in changes:
        challenge.description = changes["description"]
    if "period_type" in changes:
        challenge.period_type = changes["period_type"]
    if "event_type" in changes:
        challenge.event_type = changes["event_type"]
    if "target_value" in changes:
        challenge.target_value = changes["target_value"]
    if "reward_points" in changes:
        challenge.reward_points = changes["reward_points"]
    if "is_active" in changes:
        challenge.is_active = changes["is_active"]
    if "starts_at" in changes:
        challenge.starts_at = changes["starts_at"]
    if "ends_at" in changes:
        challenge.ends_at = changes["ends_at"]

    challenge.updated_at = now_utc_naive()
    await session.flush()
    await session.refresh(challenge)
    return challenge


async def delete_challenge(session: AsyncSession, challenge_id: int) -> bool:
    challenge = await get_challenge(session, challenge_id)
    if challenge is None:
        return False
    await session.delete(challenge)
    await session.flush()
    return True


async def list_active_challenges(
    session: AsyncSession,
    *,
    moment: datetime | None = None,
    event_type: str | None = None,
) -> list[Challenge]:
    now = moment or now_utc_naive()
    stmt = select(Challenge).where(
        Challenge.is_active.is_(True),
        or_(Challenge.starts_at.is_(None), Challenge.starts_at <= now),
        or_(Challenge.ends_at.is_(None), Challenge.ends_at >= now),
    )
    if event_type is not None:
        stmt = stmt.where(Challenge.event_type == event_type)
    stmt = stmt.order_by(Challenge.id.asc())
    return list((await session.execute(stmt)).scalars().all())


async def get_user_challenge_progress(
    session: AsyncSession,
    *,
    user_id: int,
    challenge_id: int,
    period_key: str,
) -> UserChallengeProgress | None:
    stmt = (
        select(UserChallengeProgress)
        .where(
            UserChallengeProgress.user_id == user_id,
            UserChallengeProgress.challenge_id == challenge_id,
            UserChallengeProgress.period_key == period_key,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def create_user_challenge_progress(
    session: AsyncSession,
    *,
    user_id: int,
    challenge_id: int,
    period_key: str,
    progress_value: int = 0,
) -> UserChallengeProgress:
    now = now_utc_naive()
    progress = UserChallengeProgress(
        user_id=user_id,
        challenge_id=challenge_id,
        period_key=period_key,
        progress_value=progress_value,
        created_at=now,
        updated_at=now,
    )
    session.add(progress)
    await session.flush()
    return progress


async def get_user_challenge_claim(
    session: AsyncSession,
    *,
    user_id: int,
    challenge_id: int,
    period_key: str,
) -> UserChallengeClaim | None:
    stmt = (
        select(UserChallengeClaim)
        .where(
            UserChallengeClaim.user_id == user_id,
            UserChallengeClaim.challenge_id == challenge_id,
            UserChallengeClaim.period_key == period_key,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def create_user_challenge_claim(
    session: AsyncSession,
    *,
    user_id: int,
    challenge_id: int,
    period_key: str,
    reward_points: float,
    ledger_entry_id: int | None,
) -> UserChallengeClaim:
    now = now_utc_naive()
    claim = UserChallengeClaim(
        user_id=user_id,
        challenge_id=challenge_id,
        period_key=period_key,
        reward_points=reward_points,
        ledger_entry_id=ledger_entry_id,
        claimed_at=now,
    )
    session.add(claim)
    await session.flush()
    return claim


async def list_user_progress_for_challenges(
    session: AsyncSession,
    *,
    user_id: int,
    challenge_ids: Sequence[int],
    period_keys: Sequence[str],
) -> list[UserChallengeProgress]:
    if not challenge_ids or not period_keys:
        return []
    stmt = select(UserChallengeProgress).where(
        UserChallengeProgress.user_id == user_id,
        UserChallengeProgress.challenge_id.in_(list(challenge_ids)),
        UserChallengeProgress.period_key.in_(list(period_keys)),
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_user_claims_for_challenges(
    session: AsyncSession,
    *,
    user_id: int,
    challenge_ids: Sequence[int],
    period_keys: Sequence[str],
) -> list[UserChallengeClaim]:
    if not challenge_ids or not period_keys:
        return []
    stmt = select(UserChallengeClaim).where(
        UserChallengeClaim.user_id == user_id,
        UserChallengeClaim.challenge_id.in_(list(challenge_ids)),
        UserChallengeClaim.period_key.in_(list(period_keys)),
    )
    return list((await session.execute(stmt)).scalars().all())
