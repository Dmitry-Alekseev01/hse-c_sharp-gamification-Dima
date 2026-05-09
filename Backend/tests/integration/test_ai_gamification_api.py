import pytest

from app.core.security import get_password_hash
from app.models.material import Material
from app.models.question import Question
from app.models.test_ import Test
from app.models.user import User
from app.repositories import ai_gamification_repo
from app.schemas.ai_gamification import AIGamifyDraft, AIGamifyRequest

pytestmark = pytest.mark.asyncio


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(client, username: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def seed_user(db, *, username: str, password: str, role: str) -> User:
    user = User(username=username, password_hash=get_password_hash(password), role=role)
    db.add(user)
    await db.flush()
    return user


class _FakeRedis:
    def __init__(self):
        self._counters: dict[str, int] = {}
        self._lists: dict[str, list[str]] = {}
        self._hashes: dict[str, dict[str, int]] = {}

    async def incr(self, key: str) -> int:
        next_value = self._counters.get(key, 0) + 1
        self._counters[key] = next_value
        return next_value

    async def expire(self, *_args, **_kwargs):
        return True

    async def rpush(self, key: str, value: str):
        items = self._lists.setdefault(key, [])
        items.append(value)
        return len(items)

    async def hincrby(self, key: str, field: str, amount: int):
        bucket = self._hashes.setdefault(key, {})
        next_value = int(bucket.get(field, 0)) + int(amount)
        bucket[field] = next_value
        return next_value

    async def hgetall(self, key: str):
        return dict(self._hashes.get(key, {}))

    async def llen(self, key: str):
        return len(self._lists.get(key, []))

    async def lrange(self, key: str, start: int, end: int):
        items = list(self._lists.get(key, []))
        if not items:
            return []
        safe_start = max(int(start), 0)
        safe_end = int(end)
        if safe_end < 0:
            safe_end = len(items) - 1
        return items[safe_start : safe_end + 1]

    async def delete(self, key: str):
        removed = 0
        if key in self._counters:
            self._counters.pop(key, None)
            removed = 1
        if key in self._lists:
            self._lists.pop(key, None)
            removed = 1
        if key in self._hashes:
            self._hashes.pop(key, None)
            removed = 1
        return removed


async def seed_completed_ai_job(
    db,
    *,
    created_by_user_id: int,
    source_type: str = "raw_text",
    source_id: int | None = None,
    draft_override: AIGamifyDraft | None = None,
):
    payload = AIGamifyRequest(
        source_type=source_type,
        source_id=source_id,
        raw_text="Convert this lesson to game format" if source_type == "raw_text" else None,
    )
    job = await ai_gamification_repo.create_job(
        db,
        created_by_user_id=created_by_user_id,
        payload=payload,
        source_snapshot=payload.raw_text,
    )
    await ai_gamification_repo.set_job_completed(
        db,
        job,
        draft=draft_override
        or AIGamifyDraft(
            draft_title="Mission: C# Basics",
            story_frame="You are a mentor in a coding guild.",
            task_goal="Explain key concept with one practical step.",
            game_rules=["Use one short code example", "Keep answer concise"],
            hints=["Start from simple analogy"],
            rewards={"xp": 30, "badges": ["first-mission"]},
            acceptance_criteria=["Contains clear goal", "Contains verification criteria"],
            teacher_notes="Use as warm-up.",
        ),
        model="openrouter/test",
        provider="openrouter",
        usage={"total_tokens": 77},
        latency_ms=99,
    )
    await db.flush()
    return job


async def test_ai_job_create_and_get_access_scopes(client, db, monkeypatch):
    from app.services import ai_gamification_service
    from app.core.config import settings

    monkeypatch.setattr(ai_gamification_service, "get_redis_client", lambda: _FakeRedis())
    monkeypatch.setattr(settings, "ai_gamification_enabled", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")

    owner = await seed_user(db, username="ai_owner@example.com", password="owner123", role="teacher")
    other_teacher = await seed_user(db, username="ai_other@example.com", password="other123", role="teacher")
    admin = await seed_user(db, username="ai_admin@example.com", password="admin123", role="admin")

    owner_token = await login(client, owner.username, "owner123")
    other_token = await login(client, other_teacher.username, "other123")
    admin_token = await login(client, admin.username, "admin123")

    create_response = await client.post(
        "/api/v1/ai/gamify",
        headers=auth_headers(owner_token),
        json={
            "source_type": "raw_text",
            "raw_text": "Loops in C#",
            "style": "quest",
            "tone": "friendly",
        },
    )
    assert create_response.status_code == 202, create_response.text
    job_id = create_response.json()["job_id"]

    owner_get = await client.get(f"/api/v1/ai/gamify/{job_id}", headers=auth_headers(owner_token))
    assert owner_get.status_code == 200, owner_get.text
    owner_payload = owner_get.json()
    assert owner_payload["job_id"] == job_id
    assert owner_payload["status"] in {"pending", "running", "failed", "completed"}
    assert owner_payload["input"]["source_type"] == "raw_text"

    forbidden_get = await client.get(f"/api/v1/ai/gamify/{job_id}", headers=auth_headers(other_token))
    assert forbidden_get.status_code == 403, forbidden_get.text

    admin_get = await client.get(f"/api/v1/ai/gamify/{job_id}", headers=auth_headers(admin_token))
    assert admin_get.status_code == 200, admin_get.text


async def test_ai_job_source_access_validation_for_materials(client, db, monkeypatch):
    from app.services import ai_gamification_service
    from app.core.config import settings

    monkeypatch.setattr(ai_gamification_service, "get_redis_client", lambda: _FakeRedis())
    monkeypatch.setattr(settings, "ai_gamification_enabled", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")

    owner = await seed_user(db, username="ai_material_owner@example.com", password="owner123", role="teacher")
    foreign_teacher = await seed_user(db, username="ai_material_foreign@example.com", password="other123", role="teacher")

    material = Material(title="Private material", author_id=owner.id)
    db.add(material)
    await db.flush()

    foreign_token = await login(client, foreign_teacher.username, "other123")

    forbidden_response = await client.post(
        "/api/v1/ai/gamify",
        headers=auth_headers(foreign_token),
        json={
            "source_type": "material",
            "source_id": material.id,
        },
    )
    assert forbidden_response.status_code == 403, forbidden_response.text


async def test_ai_job_daily_quota_enforced(client, db, monkeypatch):
    from app.services import ai_gamification_service
    from app.core.config import settings

    fake_redis = _FakeRedis()
    monkeypatch.setattr(ai_gamification_service, "get_redis_client", lambda: fake_redis)
    monkeypatch.setattr(settings, "ai_gamification_enabled", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_gamification_daily_quota_per_user", 1)

    teacher = await seed_user(db, username="ai_quota_teacher@example.com", password="teacher123", role="teacher")
    token = await login(client, teacher.username, "teacher123")

    first_create = await client.post(
        "/api/v1/ai/gamify",
        headers=auth_headers(token),
        json={"source_type": "raw_text", "raw_text": "first request"},
    )
    assert first_create.status_code == 202, first_create.text

    second_create = await client.post(
        "/api/v1/ai/gamify",
        headers=auth_headers(token),
        json={"source_type": "raw_text", "raw_text": "second request"},
    )
    assert second_create.status_code == 429, second_create.text


async def test_ai_apply_to_material_and_idempotent(client, db):
    teacher = await seed_user(db, username="ai_apply_teacher@example.com", password="teacher123", role="teacher")
    token = await login(client, teacher.username, "teacher123")

    material = Material(title="Networking intro", author_id=teacher.id)
    db.add(material)
    await db.flush()

    job = await seed_completed_ai_job(db, created_by_user_id=teacher.id, source_type="raw_text")

    apply_payload = {
        "target_type": "material",
        "target_id": material.id,
        "apply_mode": "append",
    }
    first_apply = await client.post(
        f"/api/v1/ai/gamify/{job.id}/apply",
        headers=auth_headers(token),
        json=apply_payload,
    )
    assert first_apply.status_code == 200, first_apply.text
    assert first_apply.json()["status"] == "applied"

    material_after_apply = await client.get(f"/api/v1/materials/{material.id}", headers=auth_headers(token))
    assert material_after_apply.status_code == 200, material_after_apply.text
    assert len(material_after_apply.json()["blocks"]) == 1

    second_apply = await client.post(
        f"/api/v1/ai/gamify/{job.id}/apply",
        headers=auth_headers(token),
        json=apply_payload,
    )
    assert second_apply.status_code == 200, second_apply.text

    material_after_second_apply = await client.get(f"/api/v1/materials/{material.id}", headers=auth_headers(token))
    assert material_after_second_apply.status_code == 200, material_after_second_apply.text
    assert len(material_after_second_apply.json()["blocks"]) == 1


async def test_ai_apply_question_replace_and_bound_target_validation(client, db):
    teacher = await seed_user(db, username="ai_question_teacher@example.com", password="teacher123", role="teacher")
    token = await login(client, teacher.username, "teacher123")

    test = Test(title="C# test", author_id=teacher.id, published=True)
    db.add(test)
    await db.flush()

    question = Question(
        test_id=test.id,
        text=(
            "Original question\n\n"
            "public delegate void ButtonClickedHandler(object sender, EventArgs e);\n"
            "public class Button { public event ButtonClickedHandler Clicked; }"
        ),
        points=1.0,
        is_open_answer=True,
    )
    db.add(question)
    await db.flush()

    job = await seed_completed_ai_job(
        db,
        created_by_user_id=teacher.id,
        source_type="question",
        source_id=question.id,
    )
    job_id = job.id
    question_id = question.id

    material = Material(title="Other target", author_id=teacher.id)
    db.add(material)
    await db.flush()
    material_id = material.id
    await db.commit()

    bound_target_error = await client.post(
        f"/api/v1/ai/gamify/{job_id}/apply",
        headers=auth_headers(token),
        json={"target_type": "material", "target_id": material_id, "apply_mode": "append"},
    )
    assert bound_target_error.status_code == 400, bound_target_error.text

    apply_response = await client.post(
        f"/api/v1/ai/gamify/{job_id}/apply",
        headers=auth_headers(token),
        json={"apply_mode": "replace"},
    )
    assert apply_response.status_code == 200, apply_response.text
    assert apply_response.json()["updated_entity"]["id"] == question_id

    question_after_apply = await client.get(f"/api/v1/questions/{question_id}", headers=auth_headers(token))
    assert question_after_apply.status_code == 200, question_after_apply.text
    assert "Mission: C# Basics" in question_after_apply.json()["text"]
    assert "public delegate void ButtonClickedHandler" in question_after_apply.json()["text"]


async def test_ai_apply_raw_text_requires_explicit_target(client, db):
    teacher = await seed_user(db, username="ai_raw_target_teacher@example.com", password="teacher123", role="teacher")
    token = await login(client, teacher.username, "teacher123")

    job = await seed_completed_ai_job(db, created_by_user_id=teacher.id, source_type="raw_text")
    await db.commit()

    response = await client.post(
        f"/api/v1/ai/gamify/{job.id}/apply",
        headers=auth_headers(token),
        json={"apply_mode": "append"},
    )
    assert response.status_code == 422, response.text


async def test_ai_apply_requires_completed_status(client, db):
    teacher = await seed_user(db, username="ai_pending_teacher@example.com", password="teacher123", role="teacher")
    token = await login(client, teacher.username, "teacher123")

    payload = AIGamifyRequest(source_type="raw_text", raw_text="Pending draft payload")
    pending_job = await ai_gamification_repo.create_job(
        db,
        created_by_user_id=teacher.id,
        payload=payload,
        source_snapshot=payload.raw_text,
    )
    await db.flush()

    material = Material(title="Pending material", author_id=teacher.id)
    db.add(material)
    await db.flush()

    response = await client.post(
        f"/api/v1/ai/gamify/{pending_job.id}/apply",
        headers=auth_headers(token),
        json={"target_type": "material", "target_id": material.id, "apply_mode": "append"},
    )
    assert response.status_code == 409, response.text


async def test_ai_apply_rejects_semantically_empty_completed_draft(client, db):
    teacher = await seed_user(db, username="ai_empty_apply_teacher@example.com", password="teacher123", role="teacher")
    token = await login(client, teacher.username, "teacher123")

    material = Material(title="Material for empty draft", author_id=teacher.id)
    db.add(material)
    await db.flush()

    job = await seed_completed_ai_job(
        db,
        created_by_user_id=teacher.id,
        source_type="raw_text",
        draft_override=AIGamifyDraft(
            draft_title="",
            story_frame="",
            task_goal="",
            game_rules=[],
            hints=[],
            rewards={"xp": 0, "badges": []},
            acceptance_criteria=[],
            teacher_notes=None,
        ),
    )
    await db.commit()

    response = await client.post(
        f"/api/v1/ai/gamify/{job.id}/apply",
        headers=auth_headers(token),
        json={"target_type": "material", "target_id": material.id, "apply_mode": "append"},
    )
    assert response.status_code == 409, response.text
    assert "semantically empty" in response.json()["detail"]


async def test_ai_list_jobs_visibility_owner_and_admin(client, db):
    owner = await seed_user(db, username="ai_list_owner@example.com", password="owner123", role="teacher")
    other = await seed_user(db, username="ai_list_other@example.com", password="other123", role="teacher")
    admin = await seed_user(db, username="ai_list_admin@example.com", password="admin123", role="admin")

    owner_token = await login(client, owner.username, "owner123")
    admin_token = await login(client, admin.username, "admin123")

    await seed_completed_ai_job(db, created_by_user_id=owner.id, source_type="raw_text")
    await seed_completed_ai_job(db, created_by_user_id=owner.id, source_type="raw_text")
    await seed_completed_ai_job(db, created_by_user_id=other.id, source_type="raw_text")
    await db.commit()

    owner_list = await client.get("/api/v1/ai/gamify?limit=20&offset=0", headers=auth_headers(owner_token))
    assert owner_list.status_code == 200, owner_list.text
    owner_items = owner_list.json()["items"]
    assert len(owner_items) == 2

    admin_list = await client.get("/api/v1/ai/gamify?limit=20&offset=0", headers=auth_headers(admin_token))
    assert admin_list.status_code == 200, admin_list.text
    admin_items = admin_list.json()["items"]
    assert len(admin_items) >= 3


async def test_ai_retry_failed_job_and_ops_metrics(client, db, monkeypatch):
    from app.services import ai_gamification_service
    from app.core.config import settings
    from app.services.ai_gamification_service import AI_GAMIFY_QUEUE

    fake_redis = _FakeRedis()
    fake_redis._hashes["ai:gamify:metrics"] = {
        "jobs_processed": 5,
        "jobs_completed": 3,
        "jobs_failed": 2,
        "jobs_retried": 1,
        "jobs_semantic_fallback_used": 4,
    }
    fake_redis._lists[AI_GAMIFY_QUEUE] = ["job-a", "job-b"]
    fake_redis._lists["ai:gamify:dlq"] = ["failed-a"]

    monkeypatch.setattr(ai_gamification_service, "get_redis_client", lambda: fake_redis)
    monkeypatch.setattr(settings, "ai_gamification_enabled", True)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")

    teacher = await seed_user(db, username="ai_retry_teacher@example.com", password="teacher123", role="teacher")
    admin = await seed_user(db, username="ai_retry_admin@example.com", password="admin123", role="admin")
    teacher_token = await login(client, teacher.username, "teacher123")
    admin_token = await login(client, admin.username, "admin123")

    failed_job = await seed_completed_ai_job(db, created_by_user_id=teacher.id, source_type="raw_text")
    await ai_gamification_repo.set_job_failed(db, failed_job, error_text="provider timeout")
    await db.commit()

    retry_response = await client.post(
        f"/api/v1/ai/gamify/{failed_job.id}/retry",
        headers=auth_headers(teacher_token),
    )
    assert retry_response.status_code == 202, retry_response.text
    assert retry_response.json()["status"] == "pending"
    assert len(fake_redis._lists.get(AI_GAMIFY_QUEUE, [])) >= 3

    metrics_for_teacher = await client.get("/api/v1/ai/ops/metrics", headers=auth_headers(teacher_token))
    assert metrics_for_teacher.status_code == 403, metrics_for_teacher.text

    metrics_for_admin = await client.get("/api/v1/ai/ops/metrics", headers=auth_headers(admin_token))
    assert metrics_for_admin.status_code == 200, metrics_for_admin.text
    payload = metrics_for_admin.json()
    assert payload["queued_jobs"] >= 3
    assert payload["dead_letter_jobs"] == 1
    assert payload["jobs_processed"] == 5
    assert payload["jobs_retried"] == 2
    assert payload["jobs_semantic_fallback_used"] == 4


async def test_ai_ops_metrics_admin_smoke_with_valid_token(client, db, monkeypatch):
    from app.services import ai_gamification_service

    fake_redis = _FakeRedis()
    fake_redis._hashes["ai:gamify:metrics"] = {
        "jobs_processed": 2,
        "jobs_completed": 1,
        "jobs_failed": 1,
        "jobs_retried": 1,
        "jobs_semantic_fallback_used": 1,
    }
    monkeypatch.setattr(ai_gamification_service, "get_redis_client", lambda: fake_redis)

    admin = await seed_user(db, username="ai_metrics_smoke_admin@example.com", password="admin123", role="admin")
    admin_token = await login(client, admin.username, "admin123")

    response = await client.get("/api/v1/ai/ops/metrics", headers=auth_headers(admin_token))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jobs_processed"] == 2
    assert payload["jobs_completed"] == 1
    assert payload["jobs_failed"] == 1
    assert payload["jobs_retried"] == 1
    assert payload["jobs_semantic_fallback_used"] == 1


async def test_ai_ops_dlq_admin_only_and_payload(client, db, monkeypatch):
    from app.services import ai_gamification_service

    fake_redis = _FakeRedis()
    fake_redis._lists["ai:gamify:dlq"] = [
        '{"job_id": 42, "error": "provider timeout"}',
        "not-json-payload",
    ]
    monkeypatch.setattr(ai_gamification_service, "get_redis_client", lambda: fake_redis)

    teacher = await seed_user(db, username="ai_dlq_teacher@example.com", password="teacher123", role="teacher")
    admin = await seed_user(db, username="ai_dlq_admin@example.com", password="admin123", role="admin")
    teacher_token = await login(client, teacher.username, "teacher123")
    admin_token = await login(client, admin.username, "admin123")

    teacher_response = await client.get("/api/v1/ai/ops/dlq", headers=auth_headers(teacher_token))
    assert teacher_response.status_code == 403, teacher_response.text

    admin_response = await client.get(
        "/api/v1/ai/ops/dlq?limit=10&offset=0",
        headers=auth_headers(admin_token),
    )
    assert admin_response.status_code == 200, admin_response.text
    payload = admin_response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert len(payload["items"]) == 2
    assert payload["items"][0]["job_id"] == 42
    assert payload["items"][0]["error"] == "provider timeout"
    assert payload["items"][0]["queue_index"] == 0
    assert payload["items"][1]["job_id"] is None
    assert payload["items"][1]["raw_payload"] == "not-json-payload"


async def test_ai_ops_dlq_requeue_and_discard(client, db, monkeypatch):
    from app.services import ai_gamification_service

    fake_redis = _FakeRedis()
    monkeypatch.setattr(ai_gamification_service, "get_redis_client", lambda: fake_redis)

    admin = await seed_user(db, username="ai_dlq_action_admin@example.com", password="admin123", role="admin")
    admin_token = await login(client, admin.username, "admin123")

    failed_job = await seed_completed_ai_job(db, created_by_user_id=admin.id, source_type="raw_text")
    await ai_gamification_repo.set_job_failed(db, failed_job, error_text="provider timeout")
    await db.commit()

    fake_redis._lists["ai:gamify:dlq"] = [
        '{"job_id": %d, "error": "provider timeout"}' % failed_job.id,
        "broken-payload",
    ]

    requeue_response = await client.post(
        "/api/v1/ai/ops/dlq/0/requeue",
        headers=auth_headers(admin_token),
    )
    assert requeue_response.status_code == 200, requeue_response.text
    requeue_payload = requeue_response.json()
    assert requeue_payload["job_id"] == failed_job.id
    assert requeue_payload["status"] == "pending"

    refreshed = await ai_gamification_repo.get_job(db, failed_job.id)
    assert refreshed is not None
    assert refreshed.status == "pending"
    assert len(fake_redis._lists.get("ai:gamify", [])) == 1

    discard_response = await client.delete(
        "/api/v1/ai/ops/dlq/0",
        headers=auth_headers(admin_token),
    )
    assert discard_response.status_code == 200, discard_response.text
    discard_payload = discard_response.json()
    assert discard_payload["queue_index"] == 0
    assert discard_payload["removed"] is True

    # DLQ should now be empty after requeue+discard actions.
    dlq_after = await client.get("/api/v1/ai/ops/dlq", headers=auth_headers(admin_token))
    assert dlq_after.status_code == 200, dlq_after.text
    assert dlq_after.json()["total"] == 0


async def test_ai_ops_dlq_batch_actions(client, db, monkeypatch):
    from app.services import ai_gamification_service

    fake_redis = _FakeRedis()
    monkeypatch.setattr(ai_gamification_service, "get_redis_client", lambda: fake_redis)

    admin = await seed_user(db, username="ai_dlq_batch_admin@example.com", password="admin123", role="admin")
    admin_token = await login(client, admin.username, "admin123")

    failed_job = await seed_completed_ai_job(db, created_by_user_id=admin.id, source_type="raw_text")
    await ai_gamification_repo.set_job_failed(db, failed_job, error_text="provider timeout")
    await db.commit()

    fake_redis._lists["ai:gamify:dlq"] = [
        '{"job_id": %d, "error": "provider timeout"}' % failed_job.id,
        "broken-payload",
        '{"job_id": 999999, "error": "unknown job"}',
    ]

    batch_requeue = await client.post(
        "/api/v1/ai/ops/dlq/requeue-batch",
        headers=auth_headers(admin_token),
        json={"max_items": 3},
    )
    assert batch_requeue.status_code == 200, batch_requeue.text
    requeue_payload = batch_requeue.json()
    assert requeue_payload["scanned"] == 3
    assert requeue_payload["requeued"] == 1
    assert requeue_payload["skipped"] == 2
    assert requeue_payload["discarded"] == 0
    assert requeue_payload["failures"] == []
    assert len(fake_redis._lists.get("ai:gamify", [])) == 1

    batch_discard = await client.post(
        "/api/v1/ai/ops/dlq/discard-batch",
        headers=auth_headers(admin_token),
        json={"max_items": 10},
    )
    assert batch_discard.status_code == 200, batch_discard.text
    discard_payload = batch_discard.json()
    assert discard_payload["discarded"] == 2
    assert discard_payload["requeued"] == 0
    assert discard_payload["skipped"] == 0

    dlq_after = await client.get("/api/v1/ai/ops/dlq", headers=auth_headers(admin_token))
    assert dlq_after.status_code == 200, dlq_after.text
    assert dlq_after.json()["total"] == 0
