from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

from app.schemas.level import LevelRead

class AnalyticsRead(BaseModel):
    user_id: int
    total_points: float
    tests_taken: int
    last_active: datetime | None
    streak_days: int
    current_level_id: int | None

    model_config = ConfigDict(from_attributes=True)

class LeaderboardEntry(BaseModel):
    user_id: int
    username: str
    total_points: float

    model_config = ConfigDict(from_attributes=True)

class TestSummary(BaseModel):
    test_id: int
    total_questions: int
    total_attempts: int
    completed_attempts: int
    avg_score: float | None
    avg_time_seconds: float | None

    model_config = ConfigDict(from_attributes=True)

class QuestionStats(BaseModel):
    question_id: int
    attempts: int
    avg_score: float | None
    correct_count: int
    correct_rate: float | None
    distinct_users: int

    model_config = ConfigDict(from_attributes=True)


class AnalyticsOverviewRead(BaseModel):
    total_users: int
    total_materials: int
    total_tests: int
    published_tests: int
    total_questions: int
    total_answers: int
    completed_attempts: int
    pending_open_answers: int
    active_users_7d: int


class UserPerformanceRead(BaseModel):
    user_id: int
    username: str
    full_name: str | None
    total_points: float
    tests_taken: int
    streak_days: int
    current_level_id: int | None
    completed_attempts: int
    avg_score: float | None
    avg_time_seconds: float | None
    last_active: datetime | None


class UserGamificationProgressRead(BaseModel):
    user_id: int
    username: str
    total_points: float
    streak_days: int
    current_level: LevelRead | None
    next_level: LevelRead | None
    points_to_next_level: float
    progress_percent: float


class GroupAnalyticsSummaryRead(BaseModel):
    group_id: int
    members_count: int
    active_members_7d: int
    total_points: float
    avg_points: float | None
    completed_attempts: int
    avg_completed_attempts: float | None
    avg_score: float | None
    avg_time_seconds: float | None


class ScoreBucketRead(BaseModel):
    label: str
    count: int
