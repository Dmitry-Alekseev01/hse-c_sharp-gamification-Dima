from datetime import datetime

from pydantic import BaseModel, ConfigDict
from typing import Literal


class TestAttemptCreate(BaseModel):
    pass


class TestAttemptRead(BaseModel):
    id: int
    user_id: int
    test_id: int
    status: str
    score: float | None
    manual_score: float | None
    max_score: float | None
    time_spent_seconds: int | None
    started_at: datetime
    submitted_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TestAttemptQuotaRead(BaseModel):
    test_id: int
    max_attempts: int
    completed_attempts: int
    remaining_attempts: int
    has_active_attempt: bool
    progress_state: Literal["not_started", "in_progress", "completed"] = "not_started"
    attempt_state: Literal["can_start", "can_resume", "blocked"] = "can_start"
    can_start: bool = True
    can_resume: bool = False
    block_reason: Literal[
        "no_attempts",
        "deadline_passed",
        "time_limit_exceeded",
        "level_locked",
        "test_unpublished",
    ] | None = None


class TestAttemptStartRead(TestAttemptRead):
    action: Literal["started", "resumed"]
    max_attempts: int
    completed_attempts: int
    remaining_attempts: int
    has_active_attempt: bool
    progress_state: Literal["not_started", "in_progress", "completed"] = "not_started"
    attempt_state: Literal["can_start", "can_resume", "blocked"] = "can_start"
    can_start: bool = True
    can_resume: bool = False
    block_reason: Literal[
        "no_attempts",
        "deadline_passed",
        "time_limit_exceeded",
        "level_locked",
        "test_unpublished",
    ] | None = None


class TestAttemptStateRead(BaseModel):
    attempt_id: int
    test_id: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    time_limit_minutes: int | None
    elapsed_seconds: int
    remaining_seconds: int | None
    is_expired: bool
    expired_reason: str | None
