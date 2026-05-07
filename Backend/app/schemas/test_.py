from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Literal

class TestCreate(BaseModel):
    __test__ = False 
    title: str
    description: str | None = None
    time_limit_minutes: int | None = None
    max_score: int | None = None
    max_attempts: int = Field(default=1, ge=1)
    published: bool = False
    material_ids: List[int] | None = None
    deadline: datetime | None = None
    required_level_id: int | None = None


class TestUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    time_limit_minutes: int | None = None
    max_score: int | None = None
    max_attempts: int | None = Field(default=None, ge=1)
    published: bool | None = None
    material_ids: List[int] | None = None
    deadline: datetime | None = None
    required_level_id: int | None = None


class TestRead(BaseModel):
    __test__ = False 
    id: int
    title: str
    description: str | None
    time_limit_minutes: int | None
    max_score: int | None
    max_attempts: int
    published: bool
    published_at: datetime | None
    material_ids: List[int]
    deadline: datetime | None
    author_id: int | None
    required_level_id: int | None

    model_config = ConfigDict(from_attributes=True)


class TestCardRead(TestRead):
    total_questions: int = 0
    user_status: Literal["not_started", "in_progress", "completed"] = "not_started"
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
    has_active_attempt: bool = False
    active_attempt_id: int | None = None
    completed_attempts: int = 0
    remaining_attempts: int = 0
    user_score: float | None = None
    user_max_score: float | None = None
    latest_completed_at: datetime | None = None
