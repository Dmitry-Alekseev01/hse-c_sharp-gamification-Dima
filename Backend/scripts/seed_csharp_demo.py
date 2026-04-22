from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.analytics import Analytics
from app.models.answer import Answer
from app.models.associations import material_test_links
from app.models.choice import Choice
from app.models.group import GroupMembership, StudyGroup
from app.models.level import Level
from app.models.material import Material
from app.models.material_attachment import MaterialAttachment
from app.models.material_block import MaterialBlock
from app.models.points_ledger import PointsLedger
from app.models.question import Question
from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.repositories import analytics_repo


DEMO_PREFIX = "[DEMO CSHARP]"
DEMO_GROUP_NAME = f"{DEMO_PREFIX} Frontend QA Group"

USERS = {
    "teacher": {
        "username": "csharp_teacher_demo@example.com",
        "password": "Teach123!",
        "full_name": "C# Demo Teacher",
        "role": "teacher",
    },
    "student": {
        "username": "csharp_student_demo@example.com",
        "password": "Stud123!",
        "full_name": "C# Demo Student",
        "role": "user",
    },
    "admin": {
        "username": "csharp_admin_demo@example.com",
        "password": "Admin123!",
        "full_name": "C# Demo Admin",
        "role": "admin",
    },
}


async def _ensure_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    full_name: str,
    role: str,
) -> User:
    user = (await session.execute(select(User).where(User.username == username))).scalars().first()
    if user is None:
        user = User(
            username=username,
            full_name=full_name,
            role=role,
            password_hash=get_password_hash(password),
        )
        session.add(user)
    else:
        user.full_name = full_name
        user.role = role
        user.password_hash = get_password_hash(password)
    await session.flush()
    return user


async def _cleanup_demo_content(session: AsyncSession) -> None:
    demo_usernames = [value["username"] for value in USERS.values()]
    demo_user_ids = list(
        (await session.execute(select(User.id).where(User.username.in_(demo_usernames)))).scalars().all()
    )
    demo_test_ids = list(
        (await session.execute(select(Test.id).where(Test.title.like(f"{DEMO_PREFIX}%")))).scalars().all()
    )
    demo_material_ids = list(
        (await session.execute(select(Material.id).where(Material.title.like(f"{DEMO_PREFIX}%")))).scalars().all()
    )
    demo_group_ids = list(
        (await session.execute(select(StudyGroup.id).where(StudyGroup.name.like(f"{DEMO_PREFIX}%")))).scalars().all()
    )
    if demo_test_ids:
        demo_question_ids = list(
            (
                await session.execute(select(Question.id).where(Question.test_id.in_(demo_test_ids)))
            ).scalars().all()
        )
        await session.execute(delete(Answer).where(Answer.test_id.in_(demo_test_ids)))
        await session.execute(delete(TestAttempt).where(TestAttempt.test_id.in_(demo_test_ids)))
        if demo_question_ids:
            await session.execute(delete(Choice).where(Choice.question_id.in_(demo_question_ids)))
            await session.execute(delete(Question).where(Question.id.in_(demo_question_ids)))
        await session.execute(delete(material_test_links).where(material_test_links.c.test_id.in_(demo_test_ids)))

    if demo_material_ids:
        await session.execute(
            delete(material_test_links).where(material_test_links.c.material_id.in_(demo_material_ids))
        )
        await session.execute(delete(MaterialBlock).where(MaterialBlock.material_id.in_(demo_material_ids)))
        await session.execute(delete(MaterialAttachment).where(MaterialAttachment.material_id.in_(demo_material_ids)))

    if demo_group_ids:
        await session.execute(delete(GroupMembership).where(GroupMembership.group_id.in_(demo_group_ids)))

    if demo_user_ids:
        await session.execute(delete(UserAchievement).where(UserAchievement.user_id.in_(demo_user_ids)))
        await session.execute(delete(PointsLedger).where(PointsLedger.user_id.in_(demo_user_ids)))
        await session.execute(delete(Analytics).where(Analytics.user_id.in_(demo_user_ids)))

    await session.flush()


async def _create_demo_levels(session: AsyncSession) -> dict[str, Level]:
    level_specs = [
        ("lvl1", f"{DEMO_PREFIX} Level 1", 0, "C# syntax basics"),
        ("lvl2", f"{DEMO_PREFIX} Level 2", 60, "OOP and interfaces"),
        ("lvl3", f"{DEMO_PREFIX} Level 3", 140, "Async and collections"),
    ]
    result: dict[str, Level] = {}
    for key, name, required_points, description in level_specs:
        level = (await session.execute(select(Level).where(Level.name == name))).scalars().first()
        if level is None:
            level = Level(
                name=name,
                required_points=required_points,
                description=description,
            )
            session.add(level)
        else:
            level.required_points = required_points
            level.description = description
        result[key] = level
    await session.flush()
    return result


def _material_data() -> list[dict]:
    return [
        {
            "title": f"{DEMO_PREFIX} 1. Intro to C# and .NET",
            "description": "CLR, SDK, project layout, and first C# program.",
            "required_level_key": "lvl1",
            "blocks": [
                {
                    "block_type": "text",
                    "title": "Key concepts",
                    "body": "C# code compiles to IL and runs on CLR.",
                    "order_index": 0,
                },
                {
                    "block_type": "documentation_link",
                    "title": "Microsoft Docs",
                    "url": "https://learn.microsoft.com/dotnet/csharp/",
                    "order_index": 1,
                },
                {
                    "block_type": "video_link",
                    "title": "Video: C# in 30 minutes",
                    "url": "https://www.youtube.com/watch?v=GhQdlIFylQ8",
                    "order_index": 2,
                },
                {
                    "block_type": "code_example",
                    "title": "Hello World",
                    "body": "Console.WriteLine(\"Hello, C# world!\");",
                    "order_index": 3,
                },
            ],
            "attachments": [
                {
                    "title": "Lecture 01 - Intro (PDF)",
                    "file_url": "https://example.com/csharp/lecture01-intro.pdf",
                    "file_kind": "pdf",
                    "order_index": 0,
                    "is_downloadable": True,
                }
            ],
        },
        {
            "title": f"{DEMO_PREFIX} 2. Classes and OOP",
            "description": "Encapsulation, inheritance, and polymorphism.",
            "required_level_key": "lvl1",
            "blocks": [
                {
                    "block_type": "text",
                    "title": "What is OOP",
                    "body": "A class defines state and behavior. An object is an instance.",
                    "order_index": 0,
                },
                {
                    "block_type": "code_example",
                    "title": "Student class",
                    "body": "public class Student { public string Name { get; set; } = string.Empty; }",
                    "order_index": 1,
                },
                {
                    "block_type": "documentation_link",
                    "title": "Classes in C#",
                    "url": "https://learn.microsoft.com/dotnet/csharp/fundamentals/types/classes",
                    "order_index": 2,
                },
            ],
            "attachments": [
                {
                    "title": "OOP slides (PPTX)",
                    "file_url": "https://example.com/csharp/oop-slides.pptx",
                    "file_kind": "pptx",
                    "order_index": 0,
                    "is_downloadable": True,
                }
            ],
        },
        {
            "title": f"{DEMO_PREFIX} 3. Interfaces and DI",
            "description": "Contracts, abstractions, and dependency injection patterns.",
            "required_level_key": "lvl2",
            "blocks": [
                {
                    "block_type": "text",
                    "title": "Why interfaces",
                    "body": "Interfaces describe behavior contracts without implementation.",
                    "order_index": 0,
                },
                {
                    "block_type": "code_example",
                    "title": "IMessageSender",
                    "body": "public interface IMessageSender { Task SendAsync(string text); }",
                    "order_index": 1,
                },
                {
                    "block_type": "video_link",
                    "title": "Dependency Injection in .NET",
                    "url": "https://www.youtube.com/watch?v=2f4l6x2w6-U",
                    "order_index": 2,
                },
            ],
            "attachments": [
                {
                    "title": "Interface practice (DOCX)",
                    "file_url": "https://example.com/csharp/interfaces-practice.docx",
                    "file_kind": "docx",
                    "order_index": 0,
                    "is_downloadable": True,
                }
            ],
        },
        {
            "title": f"{DEMO_PREFIX} 4. Async/Await and Task",
            "description": "Write non-blocking C# code with async/await.",
            "required_level_key": "lvl3",
            "blocks": [
                {
                    "block_type": "text",
                    "title": "Async basics",
                    "body": "Task represents async work; await suspends without blocking the thread.",
                    "order_index": 0,
                },
                {
                    "block_type": "code_example",
                    "title": "Async method",
                    "body": "public async Task<string> LoadAsync() => await client.GetStringAsync(url);",
                    "order_index": 1,
                },
                {
                    "block_type": "documentation_link",
                    "title": "Official async guide",
                    "url": "https://learn.microsoft.com/dotnet/csharp/asynchronous-programming/",
                    "order_index": 2,
                },
            ],
            "attachments": [],
        },
        {
            "title": f"{DEMO_PREFIX} 5. Collections and LINQ",
            "description": "List, Dictionary, filtering, projection, aggregation.",
            "required_level_key": "lvl3",
            "blocks": [
                {
                    "block_type": "text",
                    "title": "LINQ essentials",
                    "body": "Use Where, Select, GroupBy, and OrderBy for expressive data queries.",
                    "order_index": 0,
                },
                {
                    "block_type": "code_example",
                    "title": "LINQ sample",
                    "body": "var top = students.Where(s => s.Score >= 80).OrderByDescending(s => s.Score);",
                    "order_index": 1,
                },
                {
                    "block_type": "documentation_link",
                    "title": "LINQ docs",
                    "url": "https://learn.microsoft.com/dotnet/csharp/linq/",
                    "order_index": 2,
                },
            ],
            "attachments": [
                {
                    "title": "LINQ cheatsheet (PDF)",
                    "file_url": "https://example.com/csharp/linq-cheatsheet.pdf",
                    "file_kind": "pdf",
                    "order_index": 0,
                    "is_downloadable": True,
                }
            ],
        },
    ]


def _test_data(materials: list[Material]) -> list[dict]:
    return [
        {
            "title": f"{DEMO_PREFIX} Test 1: Intro and Runtime",
            "description": "Validate C# and .NET fundamentals.",
            "max_score": 10,
            "material": materials[0],
            "questions": [
                {
                    "text": "Which runtime executes IL code for C# applications?",
                    "points": 3.0,
                    "is_open_answer": False,
                    "choices": [
                        {"value": "CLR", "ordinal": 1, "is_correct": True},
                        {"value": "JVM", "ordinal": 2, "is_correct": False},
                        {"value": "Node.js", "ordinal": 3, "is_correct": False},
                    ],
                },
                {
                    "text": "Which CLI command creates a new C# console project?",
                    "points": 3.0,
                    "is_open_answer": False,
                    "choices": [
                        {"value": "dotnet new console", "ordinal": 1, "is_correct": True},
                        {"value": "npm init", "ordinal": 2, "is_correct": False},
                        {"value": "mvn archetype:generate", "ordinal": 3, "is_correct": False},
                    ],
                },
                {
                    "text": "Briefly explain compile-time vs run-time in .NET.",
                    "points": 4.0,
                    "is_open_answer": True,
                    "choices": [],
                },
            ],
        },
        {
            "title": f"{DEMO_PREFIX} Test 2: OOP",
            "description": "Classes, inheritance, polymorphism.",
            "max_score": 12,
            "material": materials[1],
            "questions": [
                {
                    "text": "What does encapsulation mean?",
                    "points": 4.0,
                    "is_open_answer": False,
                    "choices": [
                        {"value": "Hide implementation details", "ordinal": 1, "is_correct": True},
                        {"value": "Run code in parallel", "ordinal": 2, "is_correct": False},
                    ],
                },
                {
                    "text": "Choose valid auto-property syntax.",
                    "points": 4.0,
                    "is_open_answer": False,
                    "choices": [
                        {"value": "public string Name { get; set; }", "ordinal": 1, "is_correct": True},
                        {"value": "property Name: string;", "ordinal": 2, "is_correct": False},
                    ],
                },
                {
                    "text": "Give a short polymorphism example in C#.",
                    "points": 4.0,
                    "is_open_answer": True,
                    "choices": [],
                },
            ],
        },
        {
            "title": f"{DEMO_PREFIX} Test 3: Interfaces",
            "description": "Interfaces and DI principles.",
            "max_score": 10,
            "material": materials[2],
            "questions": [
                {
                    "text": "What is the primary role of an interface?",
                    "points": 5.0,
                    "is_open_answer": False,
                    "choices": [
                        {"value": "Define a behavior contract", "ordinal": 1, "is_correct": True},
                        {"value": "Create a DB table", "ordinal": 2, "is_correct": False},
                    ],
                },
                {
                    "text": "Why does DI improve testability?",
                    "points": 5.0,
                    "is_open_answer": True,
                    "choices": [],
                },
            ],
        },
        {
            "title": f"{DEMO_PREFIX} Test 4: Async/Await",
            "description": "Practical async programming in C#.",
            "max_score": 8,
            "material": materials[3],
            "questions": [
                {
                    "text": "What is typically returned by async method without value?",
                    "points": 4.0,
                    "is_open_answer": False,
                    "choices": [
                        {"value": "Task", "ordinal": 1, "is_correct": True},
                        {"value": "void only", "ordinal": 2, "is_correct": False},
                    ],
                },
                {
                    "text": "Why do we use await?",
                    "points": 4.0,
                    "is_open_answer": True,
                    "choices": [],
                },
            ],
        },
    ]


async def _create_materials(
    session: AsyncSession,
    *,
    teacher: User,
    levels: dict[str, Level],
) -> list[Material]:
    materials: list[Material] = []
    for item in _material_data():
        material = (await session.execute(select(Material).where(Material.title == item["title"]))).scalars().first()
        if material is None:
            material = Material(title=item["title"])
            session.add(material)
            await session.flush()

        material.material_type = "lesson"
        material.status = "published"
        material.description = item["description"]
        material.author_id = teacher.id
        material.required_level_id = levels[item["required_level_key"]].id
        await session.execute(delete(MaterialBlock).where(MaterialBlock.material_id == material.id))
        await session.execute(delete(MaterialAttachment).where(MaterialAttachment.material_id == material.id))
        await session.execute(delete(material_test_links).where(material_test_links.c.material_id == material.id))

        blocks = [
            MaterialBlock(
                material_id=material.id,
                block_type=block["block_type"],
                title=block.get("title"),
                body=block.get("body"),
                url=block.get("url"),
                order_index=block["order_index"],
            )
            for block in item["blocks"]
        ]
        attachments = [
            MaterialAttachment(
                material_id=material.id,
                title=attachment["title"],
                file_url=attachment["file_url"],
                file_kind=attachment["file_kind"],
                order_index=attachment["order_index"],
                is_downloadable=attachment["is_downloadable"],
            )
            for attachment in item["attachments"]
        ]
        session.add_all(blocks)
        session.add_all(attachments)
        materials.append(material)
    await session.flush()
    return materials


async def _create_tests_with_questions(
    session: AsyncSession,
    *,
    teacher: User,
    levels: dict[str, Level],
    materials: list[Material],
) -> list[Test]:
    tests: list[Test] = []
    deadline_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=365)
    for idx, item in enumerate(_test_data(materials), start=1):
        required_level_id = levels["lvl1"].id if idx <= 2 else levels["lvl2"].id
        test = (await session.execute(select(Test).where(Test.title == item["title"]))).scalars().first()
        if test is None:
            test = Test(title=item["title"])
            session.add(test)
            await session.flush()

        test.description = item["description"]
        test.max_score = item["max_score"]
        test.published = True
        test.deadline = deadline_at
        test.material_id = item["material"].id
        test.author_id = teacher.id
        test.required_level_id = required_level_id

        existing_question_ids = list(
            (await session.execute(select(Question.id).where(Question.test_id == test.id))).scalars().all()
        )
        await session.execute(delete(Answer).where(Answer.test_id == test.id))
        await session.execute(delete(TestAttempt).where(TestAttempt.test_id == test.id))
        if existing_question_ids:
            await session.execute(delete(Choice).where(Choice.question_id.in_(existing_question_ids)))
            await session.execute(delete(Question).where(Question.id.in_(existing_question_ids)))
        await session.execute(delete(material_test_links).where(material_test_links.c.test_id == test.id))
        await session.execute(
            material_test_links.insert().values(material_id=item["material"].id, test_id=test.id)
        )

        questions = [
            Question(
                test_id=test.id,
                text=question["text"],
                points=question["points"],
                is_open_answer=question["is_open_answer"],
                material_urls=["https://learn.microsoft.com/dotnet/csharp/"],
                choices=[
                    Choice(
                        value=choice["value"],
                        ordinal=choice["ordinal"],
                        is_correct=choice["is_correct"],
                    )
                    for choice in question["choices"]
                ],
            )
            for question in item["questions"]
        ]
        session.add_all(questions)
        tests.append(test)
    await session.flush()
    return tests


async def _create_demo_group(session: AsyncSession, *, teacher: User, student: User) -> StudyGroup:
    group = (await session.execute(select(StudyGroup).where(StudyGroup.name == DEMO_GROUP_NAME))).scalars().first()
    if group is None:
        group = StudyGroup(name=DEMO_GROUP_NAME, teacher_id=teacher.id)
        session.add(group)
        await session.flush()
    else:
        group.teacher_id = teacher.id
        await session.execute(delete(GroupMembership).where(GroupMembership.group_id == group.id))

    session.add(GroupMembership(group_id=group.id, user_id=student.id))
    await session.flush()
    return group


async def _seed_student_attempt_and_answers(
    session: AsyncSession,
    *,
    student: User,
    first_test: Test,
    level_id: int,
) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    started = now - timedelta(minutes=20)
    finished = now - timedelta(minutes=10)

    attempt = TestAttempt(
        user_id=student.id,
        test_id=first_test.id,
        status="completed",
        score=6.0,
        max_score=10.0,
        time_spent_seconds=600,
        started_at=started,
        submitted_at=finished,
        completed_at=finished,
    )
    session.add(attempt)
    await session.flush()

    fresh_questions = list(
        (
            await session.execute(
                select(Question).where(Question.test_id == first_test.id).order_by(Question.id.asc())
            )
        ).scalars().all()
    )
    if len(fresh_questions) < 3:
        raise RuntimeError("Demo seed expected at least 3 questions in the first test")

    q1 = fresh_questions[0]
    q2 = fresh_questions[1]
    q3 = fresh_questions[2]

    q1_correct = (
        await session.execute(
            select(Choice).where(Choice.question_id == q1.id, Choice.is_correct.is_(True)).limit(1)
        )
    ).scalars().first()
    q2_wrong = (
        await session.execute(
            select(Choice).where(Choice.question_id == q2.id, Choice.is_correct.is_(False)).limit(1)
        )
    ).scalars().first()
    if q1_correct is None or q2_wrong is None:
        raise RuntimeError("Demo seed expected both correct and wrong choices in first test")

    answers = [
        Answer(
            user_id=student.id,
            test_id=first_test.id,
            attempt_id=attempt.id,
            question_id=q1.id,
            answer_payload=str(q1_correct.id),
            score=q1.points,
            created_at=started + timedelta(minutes=2),
        ),
        Answer(
            user_id=student.id,
            test_id=first_test.id,
            attempt_id=attempt.id,
            question_id=q2.id,
            answer_payload=str(q2_wrong.id),
            score=0.0,
            created_at=started + timedelta(minutes=4),
        ),
        Answer(
            user_id=student.id,
            test_id=first_test.id,
            attempt_id=attempt.id,
            question_id=q3.id,
            answer_payload="Compilation translates C# into IL, and CLR executes IL at runtime.",
            score=None,
            created_at=started + timedelta(minutes=6),
        ),
    ]
    session.add_all(answers)
    await session.flush()

    await session.execute(delete(UserAchievement).where(UserAchievement.user_id == student.id))
    await session.execute(delete(PointsLedger).where(PointsLedger.user_id == student.id))
    await session.execute(delete(Analytics).where(Analytics.user_id == student.id))
    await session.flush()

    await analytics_repo.register_completed_attempt(session, student.id, attempt_id=attempt.id)
    await analytics_repo.apply_points_delta(
        session,
        student.id,
        6.0,
        reason_code="demo_seed_points",
        source_type="demo_seed",
        source_id=attempt.id,
        idempotency_key=f"demo_seed_points:{attempt.id}",
        metadata={"demo": True, "topic": "csharp"},
    )

    analytics = (await session.execute(select(Analytics).where(Analytics.user_id == student.id))).scalars().first()
    if analytics is not None:
        analytics.current_level_id = level_id
        await session.flush()


async def seed_demo_data() -> None:
    async with AsyncSessionLocal() as session:
        teacher = await _ensure_user(session, **USERS["teacher"])
        student = await _ensure_user(session, **USERS["student"])
        await _ensure_user(session, **USERS["admin"])

        await _cleanup_demo_content(session)
        levels = await _create_demo_levels(session)
        materials = await _create_materials(session, teacher=teacher, levels=levels)
        tests = await _create_tests_with_questions(
            session,
            teacher=teacher,
            levels=levels,
            materials=materials,
        )
        group = await _create_demo_group(session, teacher=teacher, student=student)
        await _seed_student_attempt_and_answers(
            session,
            student=student,
            first_test=tests[0],
            level_id=levels["lvl1"].id,
        )
        await session.commit()

    print("=== C# demo seed completed ===")
    print(f"Materials: {len(materials)}")
    print(f"Tests: {len(tests)}")
    print("Users:")
    print(f"  teacher: {USERS['teacher']['username']} / {USERS['teacher']['password']}")
    print(f"  student: {USERS['student']['username']} / {USERS['student']['password']}")
    print(f"  admin:   {USERS['admin']['username']} / {USERS['admin']['password']}")
    print(f"Group: {group.name}")


def main() -> None:
    asyncio.run(seed_demo_data())


if __name__ == "__main__":
    main()
