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
    max_score: float | None
    time_spent_seconds: int | None
    started_at: datetime
    submitted_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
