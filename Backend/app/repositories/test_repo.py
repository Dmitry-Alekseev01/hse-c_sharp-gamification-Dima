from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from app.models.answer import Answer
from app.models.question import Question
from app.models.test_ import Test
from app.models.material import Material
from app.models.test_attempt import TestAttempt

async def get_test(session, test_id: int):
    q = select(Test).options(selectinload(Test.materials), selectinload(Test.required_level)).where(Test.id == test_id)
    res = await session.execute(q)
    return res.scalars().first()

async def list_tests(
    session,
    published_only: bool = True,
    limit: int = 100,
    author_id: int | None = None,
):
    q = select(Test).options(selectinload(Test.materials), selectinload(Test.required_level))
    if published_only:
        q = q.where(Test.published == True)
    if author_id is not None:
        q = q.where(Test.author_id == author_id)
    q = q.limit(limit)
    res = await session.execute(q)
    return res.scalars().all()

async def create_test(
    session,
    title: str,
    description: str | None = None,
    time_limit_minutes: int | None = None,
    max_score: int | None = None,
    published: bool = False,
    material_id: int | None = None,
    material_ids: list[int] | None = None,
    deadline=None,
    author_id: int | None = None,
    required_level_id: int | None = None,
):
    test = Test(
        title=title,
        description=description,
        time_limit_minutes=time_limit_minutes,
        max_score=max_score,
        published=published,
        material_id=material_id,
        deadline=deadline,
        author_id=author_id,
        required_level_id=required_level_id,
    )
    session.add(test)
    await session.flush()
    resolved_material_ids = list(dict.fromkeys([mid for mid in (material_ids or []) if mid is not None]))
    if material_id is not None and material_id not in resolved_material_ids:
        resolved_material_ids.append(material_id)
    if resolved_material_ids:
        materials = (
            await session.execute(select(Material).where(Material.id.in_(resolved_material_ids)))
        ).scalars().all()
        test.materials = materials
        await session.flush()
    await session.refresh(test)
    return test


async def update_test(
    session,
    test_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    time_limit_minutes: int | None = None,
    max_score: int | None = None,
    published: bool | None = None,
    material_id: int | None = None,
    material_ids: list[int] | None = None,
    deadline=None,
    required_level_id: int | None = None,
):
    test = await get_test(session, test_id)
    if test is None:
        return None

    if title is not None:
        test.title = title
    if description is not None:
        test.description = description
    if time_limit_minutes is not None:
        test.time_limit_minutes = time_limit_minutes
    if max_score is not None:
        test.max_score = max_score
    if published is not None:
        test.published = published
    if material_id is not None:
        test.material_id = material_id
    if deadline is not None:
        test.deadline = deadline
    if required_level_id is not None:
        test.required_level_id = required_level_id
    if material_ids is not None:
        resolved_material_ids = list(dict.fromkeys([mid for mid in material_ids if mid is not None]))
        if material_id is not None and material_id not in resolved_material_ids:
            resolved_material_ids.append(material_id)
        materials = (
            await session.execute(select(Material).where(Material.id.in_(resolved_material_ids)))
        ).scalars().all() if resolved_material_ids else []
        test.materials = materials

    await session.flush()
    await session.refresh(test)
    return test


async def delete_test(session, test_id: int) -> bool:
    test = await get_test(session, test_id)
    if test is None:
        return False
    await session.delete(test)
    await session.flush()
    return True

async def get_test_summary(session, test_id: int):
    """
    Return summary stats for a test:
    - total_questions
    - total_attempts (answers)
    - avg_score_per_attempt (overall)
    - completion_rate (approx)
    """
    attempts_agg = (
        select(
            func.count(TestAttempt.id).label("total_attempts"),
            func.sum(case((TestAttempt.status == "completed", 1), else_=0)).label("completed_attempts"),
            func.avg(case((TestAttempt.status == "completed", TestAttempt.score), else_=None)).label("avg_score"),
            func.avg(case((TestAttempt.status == "completed", TestAttempt.time_spent_seconds), else_=None)).label(
                "avg_time_seconds"
            ),
        )
        .where(TestAttempt.test_id == test_id)
        .subquery()
    )
    answers_agg = (
        select(
            func.count(func.distinct(Answer.attempt_id)).label("fallback_attempts"),
            func.avg(Answer.score).label("fallback_avg_score"),
        )
        .where(
            Answer.test_id == test_id,
            Answer.attempt_id.is_not(None),
        )
        .subquery()
    )
    stmt = select(
        select(func.count(Question.id)).where(Question.test_id == test_id).scalar_subquery().label("total_questions"),
        attempts_agg.c.total_attempts,
        attempts_agg.c.completed_attempts,
        attempts_agg.c.avg_score,
        attempts_agg.c.avg_time_seconds,
        answers_agg.c.fallback_attempts,
        answers_agg.c.fallback_avg_score,
    )
    row = (await session.execute(stmt)).mappings().first()
    total_q = int(row["total_questions"] or 0)
    total_attempts = int(row["total_attempts"] or 0)
    if total_attempts == 0:
        total_attempts = int(row["fallback_attempts"] or 0)
    completed_attempts = int(row["completed_attempts"] or 0)
    avg_score = row["avg_score"]
    if avg_score is None:
        avg_score = row["fallback_avg_score"]
    avg_time = row["avg_time_seconds"]
    return {
        "test_id": test_id,
        "total_questions": total_q,
        "total_attempts": total_attempts,
        "completed_attempts": completed_attempts,
        "avg_score": float(avg_score) if avg_score is not None else None,
        "avg_time_seconds": float(avg_time) if avg_time is not None else None,
    }
