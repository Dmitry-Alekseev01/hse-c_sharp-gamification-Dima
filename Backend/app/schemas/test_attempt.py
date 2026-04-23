from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
