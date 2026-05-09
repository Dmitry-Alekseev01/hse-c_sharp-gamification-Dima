from typing import Any

from sqlalchemy import select
from starlette.requests import Request
from starlette_admin.actions import row_action
from starlette_admin.exceptions import ActionFailed

from app.cache.redis_cache import NS_TEST_SUMMARY, bump_cache_namespace, bump_user_attempts_state_version
from app.db.session import AsyncSessionLocal
from app.models.answer import Answer
from app.models.analytics import Analytics
from app.models.points_ledger import PointsLedger
from app.models.test_ import Test
from app.models.test_attempt import TestAttempt
from app.models.user_achievement import UserAchievement
from app.models.user_reward import UserReward
from app.repositories import test_attempt_repo
from app.schemas.grading import AttemptScoreUpdate, GradeRequest
from app.services.answer_service import manual_grade_open_answer as manual_grade_open_answer_service

from .views_base import ReadOnlyAdminView, TeacherScopedByTestReadOnlyView


class AnalyticsReadOnlyView(ReadOnlyAdminView):
    name = "Analytics"
    icon = "fa fa-chart-line"
    fields = ["id", "user_id", "total_points", "tests_taken", "last_active", "streak_days", "current_level_id"]
    sortable_fields = ["id", "user_id", "total_points", "tests_taken", "streak_days", "current_level_id", "last_active"]


class TestAttemptReadOnlyView(TeacherScopedByTestReadOnlyView):
    name = "Test Attempts"
    icon = "fa fa-stopwatch"
    row_actions = ["view", "set_manual_score"]
    fields = [
        "id",
        "user_id",
        "test_id",
        "status",
        "score",
        "manual_score",
        "max_score",
        "time_spent_seconds",
        "started_at",
        "submitted_at",
        "completed_at",
    ]
    sortable_fields = [
        "id",
        "user_id",
        "test_id",
        "status",
        "score",
        "max_score",
        "time_spent_seconds",
        "started_at",
        "completed_at",
    ]

    _SCORE_ACTION_FORM = """
<form>
  <div class="mb-3">
    <label class="form-label" for="manual-score-input">Manual score</label>
    <input id="manual-score-input" class="form-control" type="number" min="0" step="0.01" name="score" required>
  </div>
</form>
""".strip()

    @row_action(
        name="set_manual_score",
        text="Set score",
        confirmation="Set manual score for this attempt?",
        icon_class="fa fa-pen",
        submit_btn_text="Apply score",
        submit_btn_class="btn-primary",
        action_btn_class="btn-outline-primary",
        form=_SCORE_ACTION_FORM,
    )
    async def set_manual_score_row_action(self, request: Request, pk: Any) -> str:
        attempt = await self.find_by_pk(request, pk)
        if attempt is None:
            raise ActionFailed("Attempt not found")

        if self._is_teacher(request):
            teacher_stmt = select(Test.id).where(Test.id == attempt.test_id, Test.author_id == self._teacher_id(request))
            if await self._scalar_one_or_none(request, teacher_stmt) is None:
                raise ActionFailed("Insufficient permissions")

        if attempt.status != "completed":
            raise ActionFailed("Attempt must be completed before final grading")

        form_data = await request.form()
        raw_score = form_data.get("score")
        try:
            score_value = float(str(raw_score))
        except (TypeError, ValueError):
            raise ActionFailed("Score must be a number")

        try:
            payload = AttemptScoreUpdate(score=score_value)
            async with AsyncSessionLocal() as session:
                try:
                    db_attempt = await test_attempt_repo.get_attempt(session, int(attempt.id))
                    if db_attempt is None:
                        raise ActionFailed("Attempt not found")
                    if db_attempt.status != "completed":
                        raise ActionFailed("Attempt must be completed before final grading")
                    if db_attempt.max_score is None:
                        db_attempt = await test_attempt_repo.refresh_attempt_scores(session, db_attempt)

                    max_score = float(db_attempt.max_score or 0.0)
                    if payload.score < 0 or payload.score > max_score:
                        raise ActionFailed(f"Score must be between 0 and {max_score}")

                    updated_attempt = await test_attempt_repo.set_manual_score(session, db_attempt, payload.score)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

            try:
                await bump_user_attempts_state_version(updated_attempt.user_id)
            except Exception:
                pass
            try:
                await bump_cache_namespace(NS_TEST_SUMMARY)
            except Exception:
                pass
            return f"Manual score updated for attempt #{updated_attempt.id}"
        except Exception as exc:
            raise ActionFailed(self._humanize_action_error(exc))


class AnswerReadOnlyView(TeacherScopedByTestReadOnlyView):
    name = "Answers"
    icon = "fa fa-reply"
    row_actions = ["view", "grade_answer"]
    fields = [
        "id",
        "user_id",
        "test_id",
        "attempt_id",
        "question_id",
        "answer_payload",
        "score",
        "graded_by",
        "graded_at",
        "created_at",
    ]
    sortable_fields = ["id", "user_id", "test_id", "question_id", "score", "graded_by", "graded_at", "created_at"]

    _GRADE_ACTION_FORM = """
<form>
  <div class="mb-3">
    <label class="form-label" for="answer-score-input">Score</label>
    <input id="answer-score-input" class="form-control" type="number" min="0" step="0.01" name="score" required>
  </div>
</form>
""".strip()

    @row_action(
        name="grade_answer",
        text="Grade",
        confirmation="Apply manual grade to this answer?",
        icon_class="fa fa-check",
        submit_btn_text="Apply grade",
        submit_btn_class="btn-success",
        action_btn_class="btn-outline-success",
        form=_GRADE_ACTION_FORM,
    )
    async def grade_answer_row_action(self, request: Request, pk: Any) -> str:
        answer = await self.find_by_pk(request, pk)
        if answer is None:
            raise ActionFailed("Answer not found")

        if self._is_teacher(request):
            teacher_stmt = select(Test.id).where(Test.id == answer.test_id, Test.author_id == self._teacher_id(request))
            if await self._scalar_one_or_none(request, teacher_stmt) is None:
                raise ActionFailed("Insufficient permissions")

        form_data = await request.form()
        raw_score = form_data.get("score")
        try:
            score_value = float(str(raw_score))
        except (TypeError, ValueError):
            raise ActionFailed("Score must be a number")

        admin_user = getattr(request.state, "admin_user", None)
        grader_id = self._to_int_or_none(getattr(admin_user, "id", None))
        if grader_id is None:
            raise ActionFailed("Unable to resolve grader identity")

        try:
            payload = GradeRequest(score=score_value)
            async with AsyncSessionLocal() as session:
                try:
                    await manual_grade_open_answer_service(
                        session,
                        answer_id=int(answer.id),
                        grader_id=grader_id,
                        score=payload.score,
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
            return f"Answer #{answer.id} was graded successfully"
        except Exception as exc:
            raise ActionFailed(self._humanize_action_error(exc))


class PointsLedgerReadOnlyView(ReadOnlyAdminView):
    name = "Points Ledger"
    icon = "fa fa-coins"
    fields = ["id", "user_id", "delta", "reason_code", "source_type", "source_id", "idempotency_key", "created_at"]
    sortable_fields = ["id", "user_id", "delta", "reason_code", "source_type", "source_id", "created_at"]


class UserAchievementReadOnlyView(ReadOnlyAdminView):
    name = "User Achievements"
    icon = "fa fa-award"
    fields = ["id", "user_id", "achievement_id", "source_event", "earned_at"]
    sortable_fields = ["id", "user_id", "achievement_id", "earned_at"]


class UserRewardReadOnlyView(ReadOnlyAdminView):
    name = "User Rewards"
    icon = "fa fa-medal"
    fields = ["id", "user_id", "reward_definition_id", "source_type", "source_ref", "earned_at"]
    sortable_fields = ["id", "user_id", "reward_definition_id", "source_type", "earned_at"]
