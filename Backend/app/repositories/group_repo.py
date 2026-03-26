from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.group import StudyGroup, GroupMembership
from app.models.user import User


async def create_group(session, name: str, teacher_id: int) -> StudyGroup:
    group = StudyGroup(name=name, teacher_id=teacher_id)
    session.add(group)
    await session.flush()
    await session.refresh(group)
    return group


async def list_groups_for_teacher(session, teacher_id: int):
    stmt = (
        select(StudyGroup)
        .options(selectinload(StudyGroup.memberships).selectinload(GroupMembership.user))
        .where(StudyGroup.teacher_id == teacher_id)
        .order_by(StudyGroup.name.asc())
    )
    res = await session.execute(stmt)
    return res.scalars().all()


async def list_all_groups(session):
    stmt = (
        select(StudyGroup)
        .options(selectinload(StudyGroup.memberships).selectinload(GroupMembership.user))
        .order_by(StudyGroup.name.asc())
    )
    res = await session.execute(stmt)
    return res.scalars().all()


async def get_group(session, group_id: int) -> StudyGroup | None:
    stmt = (
        select(StudyGroup)
        .options(selectinload(StudyGroup.memberships).selectinload(GroupMembership.user))
        .where(StudyGroup.id == group_id)
    )
    res = await session.execute(stmt)
    return res.scalars().first()


async def delete_group(session, group_id: int) -> bool:
    group = await session.get(StudyGroup, group_id)
    if group is None:
        return False
    await session.delete(group)
    await session.flush()
    return True


async def add_user_to_group(session, group: StudyGroup, user_id: int) -> GroupMembership:
    existing_stmt = select(GroupMembership).where(GroupMembership.group_id == group.id, GroupMembership.user_id == user_id)
    existing = (await session.execute(existing_stmt)).scalars().first()
    if existing is not None:
        return existing

    user = await session.get(User, user_id)
    if user is None:
        raise LookupError("User not found")

    membership = GroupMembership(group_id=group.id, user_id=user_id)
    session.add(membership)
    await session.flush()
    await session.refresh(membership)
    return membership


async def remove_user_from_group(session, group: StudyGroup, user_id: int) -> bool:
    stmt = select(GroupMembership).where(GroupMembership.group_id == group.id, GroupMembership.user_id == user_id)
    membership = (await session.execute(stmt)).scalars().first()
    if membership is None:
        return False
    await session.delete(membership)
    await session.flush()
    return True
